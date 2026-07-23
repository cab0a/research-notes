"""Deterministic JPEG codec adapters and marker-level structure parsing."""

from __future__ import annotations

import hashlib
import io
import subprocess
from dataclasses import dataclass
from typing import TypeAlias

import cv2
import imageio_ffmpeg
import numpy as np
from numpy.typing import NDArray
from PIL import Image


QuantizationTables: TypeAlias = dict[int, tuple[int, ...]]

_OPENCV_SAMPLING_FACTORS = {
    "444": cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
    "420": cv2.IMWRITE_JPEG_SAMPLING_FACTOR_420,
}
_PILLOW_SAMPLING_FACTORS = {
    "444": "4:4:4",
    "420": "4:2:0",
}
_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}
ZIGZAG_TO_NATURAL = (
    0,
    1,
    8,
    16,
    9,
    2,
    3,
    10,
    17,
    24,
    32,
    25,
    18,
    11,
    4,
    5,
    12,
    19,
    26,
    33,
    40,
    48,
    41,
    34,
    27,
    20,
    13,
    6,
    7,
    14,
    21,
    28,
    35,
    42,
    49,
    56,
    57,
    50,
    43,
    36,
    29,
    22,
    15,
    23,
    30,
    37,
    44,
    51,
    58,
    59,
    52,
    45,
    38,
    31,
    39,
    46,
    53,
    60,
    61,
    54,
    47,
    55,
    62,
    63,
)


@dataclass(frozen=True)
class JPEGQuantizationTable:
    """One DQT table in encoded zigzag order."""

    table_id: int
    precision_bits: int
    values_zigzag: tuple[int, ...]

    @property
    def values_natural(self) -> tuple[int, ...]:
        """Return the 8 x 8 table flattened in natural row-major order."""
        values = [0] * 64
        for zigzag_index, natural_index in enumerate(ZIGZAG_TO_NATURAL):
            values[natural_index] = self.values_zigzag[zigzag_index]
        return tuple(values)

    @property
    def fingerprint(self) -> str:
        """Return a stable SHA-256 fingerprint for the table definition."""
        payload = bytearray((self.table_id, self.precision_bits))
        for value in self.values_zigzag:
            payload.extend(value.to_bytes(2, "big"))
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class JPEGComponent:
    """One component definition extracted from a start-of-frame marker."""

    component_id: int
    horizontal_sampling: int
    vertical_sampling: int
    quantization_table_id: int


@dataclass(frozen=True)
class JPEGStructure:
    """JPEG dimensions, frame type, DQT tables, and component sampling."""

    frame_marker: int
    precision_bits: int
    width: int
    height: int
    quantization_tables: tuple[JPEGQuantizationTable, ...]
    components: tuple[JPEGComponent, ...]

    @property
    def quantization_fingerprint(self) -> str:
        """Return a stable fingerprint of all sorted DQT definitions."""
        digest = hashlib.sha256()
        for table in self.quantization_tables:
            digest.update(bytes.fromhex(table.fingerprint))
        return digest.hexdigest()

    @property
    def component_signature(self) -> str:
        """Return a compact component, sampling, and DQT selector signature."""
        return ";".join(
            (
                f"{component.component_id}:"
                f"{component.horizontal_sampling}x"
                f"{component.vertical_sampling}:q"
                f"{component.quantization_table_id}"
            )
            for component in self.components
        )

    def quantization_tables_natural(self) -> QuantizationTables:
        """Return DQT values in the natural ordering accepted by Pillow."""
        return {
            table.table_id: table.values_natural
            for table in self.quantization_tables
        }


@dataclass(frozen=True)
class JPEGSyntaxSummary:
    """Marker-level syntax properties across all scans in a JPEG stream."""

    frame_marker: int
    scan_count: int
    restart_interval: int
    restart_marker_count: int
    jfif_present: bool
    adobe_transform: int | None

    @property
    def frame_process(self) -> str:
        """Return a compact name for the observed frame process."""
        if self.frame_marker == 0xC0:
            return "baseline_sequential"
        if self.frame_marker == 0xC2:
            return "progressive_dct"
        return f"sof_{self.frame_marker:02x}"


def _validate_image(image: NDArray[np.generic]) -> NDArray[np.uint8]:
    """Return a validated 8-bit grayscale or BGR image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0 or (
        image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3)
    ):
        raise ValueError("image must be a non-empty grayscale or BGR array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image


def _validate_quality(quality: int) -> None:
    """Validate a numeric JPEG quality control."""
    if not isinstance(quality, int) or isinstance(quality, bool):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be in the interval [1, 100]")


def _validate_sampling(image: NDArray[np.uint8], chroma_sampling: str | None) -> None:
    """Validate the optional color sampling control."""
    if image.ndim == 2:
        if chroma_sampling is not None:
            raise ValueError("chroma_sampling applies only to BGR images")
        return
    if chroma_sampling not in _OPENCV_SAMPLING_FACTORS:
        supported = ", ".join(sorted(_OPENCV_SAMPLING_FACTORS))
        raise ValueError(f"chroma_sampling must be one of: {supported}")


def encode_jpeg_opencv(
    image: NDArray[np.generic],
    quality: int,
    chroma_sampling: str | None = None,
    *,
    optimize: bool = False,
    progressive: bool = False,
    restart_interval: int = 0,
) -> bytes:
    """Encode one JPEG with OpenCV and declared structural controls."""
    validated = _validate_image(image)
    _validate_quality(quality)
    _validate_sampling(validated, chroma_sampling)
    if not isinstance(optimize, bool):
        raise TypeError("optimize must be a boolean")
    if not isinstance(progressive, bool):
        raise TypeError("progressive must be a boolean")
    _validate_restart_interval(restart_interval)
    parameters = [
        cv2.IMWRITE_JPEG_QUALITY,
        quality,
        cv2.IMWRITE_JPEG_OPTIMIZE,
        int(optimize),
    ]
    if chroma_sampling is not None:
        parameters.extend(
            [
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
                _OPENCV_SAMPLING_FACTORS[chroma_sampling],
            ]
        )
    if progressive:
        parameters.extend([cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    if restart_interval:
        parameters.extend(
            [cv2.IMWRITE_JPEG_RST_INTERVAL, restart_interval]
        )
    succeeded, encoded = cv2.imencode(".jpg", validated, parameters)
    if not succeeded:
        raise RuntimeError("OpenCV JPEG encoding failed")
    return encoded.tobytes()


def encode_jpeg_pillow(
    image: NDArray[np.generic],
    quality: int | None,
    chroma_sampling: str | None = None,
    *,
    quantization_tables: QuantizationTables | None = None,
    optimize: bool = False,
    progressive: bool = False,
    restart_interval: int = 0,
) -> bytes:
    """Encode one JPEG with Pillow using quality or explicit DQT."""
    validated = _validate_image(image)
    _validate_sampling(validated, chroma_sampling)
    if not isinstance(optimize, bool):
        raise TypeError("optimize must be a boolean")
    if not isinstance(progressive, bool):
        raise TypeError("progressive must be a boolean")
    _validate_restart_interval(restart_interval)
    if (quality is None) == (quantization_tables is None):
        raise ValueError(
            "provide exactly one of quality or quantization_tables"
        )
    if quality is not None:
        _validate_quality(quality)
    if quantization_tables is not None:
        quantization_tables = _validate_quantization_tables(
            quantization_tables
        )

    if validated.ndim == 2:
        pillow_image = Image.fromarray(validated, mode="L")
    else:
        rgb = cv2.cvtColor(validated, cv2.COLOR_BGR2RGB)
        pillow_image = Image.fromarray(rgb, mode="RGB")
    parameters: dict[str, object] = {
        "format": "JPEG",
        "optimize": optimize,
        "progressive": progressive,
    }
    if quality is not None:
        parameters["quality"] = quality
    if quantization_tables is not None:
        parameters["qtables"] = quantization_tables
    if chroma_sampling is not None:
        parameters["subsampling"] = _PILLOW_SAMPLING_FACTORS[
            chroma_sampling
        ]
    if restart_interval:
        parameters["restart_marker_blocks"] = restart_interval
    buffer = io.BytesIO()
    pillow_image.save(buffer, **parameters)
    return buffer.getvalue()


def encode_jpeg_cmyk_pillow(
    image: NDArray[np.generic],
    quality: int,
    *,
    progressive: bool = False,
    restart_interval: int = 0,
) -> bytes:
    """Encode a four-channel synthetic CMYK array through Pillow."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0 or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("image must be a non-empty four-channel CMYK array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    _validate_quality(quality)
    if not isinstance(progressive, bool):
        raise TypeError("progressive must be a boolean")
    _validate_restart_interval(restart_interval)
    parameters: dict[str, object] = {
        "format": "JPEG",
        "quality": quality,
        "progressive": progressive,
        "optimize": False,
    }
    if restart_interval:
        parameters["restart_marker_blocks"] = restart_interval
    buffer = io.BytesIO()
    Image.fromarray(image, mode="CMYK").save(buffer, **parameters)
    return buffer.getvalue()


def _validate_restart_interval(restart_interval: int) -> None:
    """Validate a restart interval expressed in MCU blocks."""
    if not isinstance(restart_interval, int) or isinstance(
        restart_interval, bool
    ):
        raise TypeError("restart_interval must be an integer")
    if not 0 <= restart_interval <= 65535:
        raise ValueError("restart_interval must be in the interval [0, 65535]")


def _validate_quantization_tables(
    quantization_tables: QuantizationTables,
) -> QuantizationTables:
    """Return validated natural-order 8-bit quantization tables."""
    if not isinstance(quantization_tables, dict) or not quantization_tables:
        raise TypeError("quantization_tables must be a non-empty dictionary")
    validated: QuantizationTables = {}
    for table_id, values in quantization_tables.items():
        if not isinstance(table_id, int) or isinstance(table_id, bool):
            raise TypeError("quantization table identifiers must be integers")
        if not 0 <= table_id <= 3:
            raise ValueError("quantization table identifiers must be in [0, 3]")
        if len(values) != 64:
            raise ValueError("each quantization table must contain 64 values")
        converted = tuple(int(value) for value in values)
        if any(value < 1 or value > 255 for value in converted):
            raise ValueError("8-bit quantization values must be in [1, 255]")
        validated[table_id] = converted
    return validated


def decode_jpeg_opencv(
    jpeg_bytes: bytes,
    *,
    grayscale: bool = False,
    ignore_orientation: bool = False,
) -> NDArray[np.uint8]:
    """Decode JPEG bytes through OpenCV with an explicit orientation policy."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError("jpeg_bytes must be non-empty bytes")
    if not isinstance(ignore_orientation, bool):
        raise TypeError("ignore_orientation must be a boolean")
    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    if ignore_orientation:
        flag |= cv2.IMREAD_IGNORE_ORIENTATION
    decoded = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), flag)
    if decoded is None:
        raise ValueError("OpenCV could not decode the JPEG data")
    return decoded


def decode_jpeg_pillow(
    jpeg_bytes: bytes, *, grayscale: bool = False
) -> NDArray[np.uint8]:
    """Decode JPEG bytes through Pillow to grayscale or BGR pixels."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError("jpeg_bytes must be non-empty bytes")
    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            if grayscale:
                return np.asarray(image.convert("L"), dtype=np.uint8).copy()
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    except (OSError, SyntaxError) as error:
        raise ValueError("Pillow could not decode the JPEG data") from error
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def decode_jpeg_ffmpeg(
    jpeg_bytes: bytes, *, ignore_orientation: bool = False
) -> NDArray[np.uint8]:
    """Decode JPEG bytes through FFmpeg with an orientation policy."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError("jpeg_bytes must be non-empty bytes")
    if not isinstance(ignore_orientation, bool):
        raise TypeError("ignore_orientation must be a boolean")
    structure = parse_jpeg_structure(jpeg_bytes)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-threads",
        "1",
        "-c:v",
        "mjpeg",
        "-f",
        "mjpeg",
    ]
    if ignore_orientation:
        command.append("-noautorotate")
    command.extend(
        [
            "-i",
            "pipe:0",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ]
    )
    completed = subprocess.run(
        command,
        input=jpeg_bytes,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"FFmpeg could not decode the JPEG data: {message}")
    output_height = structure.height
    output_width = structure.width
    if not ignore_orientation:
        try:
            with Image.open(io.BytesIO(jpeg_bytes)) as image:
                orientation = int(image.getexif().get(274, 1))
        except (OSError, SyntaxError, TypeError, ValueError):
            orientation = 1
        if orientation in (5, 6, 7, 8):
            output_height, output_width = output_width, output_height
    expected_size = output_width * output_height * 3
    if len(completed.stdout) != expected_size:
        raise ValueError("FFmpeg returned an unexpected BGR byte count")
    return np.frombuffer(completed.stdout, dtype=np.uint8).reshape(
        output_height, output_width, 3
    ).copy()


def ffmpeg_build_information() -> dict[str, str]:
    """Return stable FFmpeg adapter and native MJPEG build metadata."""
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    version_output = subprocess.run(
        [executable, "-version"],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()
    decoder_output = subprocess.run(
        [executable, "-hide_banner", "-decoders"],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout
    if not any(
        line.split()[1:2] == ["mjpeg"]
        for line in decoder_output.splitlines()
        if line.strip().startswith("V")
    ):
        raise RuntimeError("The bundled FFmpeg build has no MJPEG decoder")
    version_line = next(
        line for line in version_output if line.startswith("ffmpeg version ")
    )
    configuration = next(
        (line for line in version_output if line.startswith("configuration:")),
        "configuration:not_reported",
    )
    return {
        "adapter": "imageio-ffmpeg",
        "adapter_version": imageio_ffmpeg.__version__,
        "codec_family": "ffmpeg-native-mjpeg",
        "codec_version": version_line.split()[2],
        "codec_build_fingerprint": hashlib.sha256(
            configuration.encode("utf-8")
        ).hexdigest(),
    }


def parse_jpeg_structure(jpeg_bytes: bytes) -> JPEGStructure:
    """Parse DQT and SOF markers from a complete JPEG byte stream."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError("jpeg_bytes must be non-empty bytes")
    if len(jpeg_bytes) < 4 or jpeg_bytes[:2] != b"\xff\xd8":
        raise ValueError("data does not begin with a JPEG SOI marker")

    tables: dict[int, JPEGQuantizationTable] = {}
    frame: tuple[int, int, int, int, tuple[JPEGComponent, ...]] | None = None
    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker == 0xD9:
            break
        if marker == 0xDA:
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment length")
        segment_length = int.from_bytes(
            jpeg_bytes[position : position + 2], "big"
        )
        if segment_length < 2:
            raise ValueError("invalid JPEG segment length")
        payload_start = position + 2
        payload_end = position + segment_length
        if payload_end > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment")
        payload = jpeg_bytes[payload_start:payload_end]
        position = payload_end
        if marker == 0xDB:
            for table in _parse_dqt_payload(payload):
                if table.table_id in tables:
                    raise ValueError("duplicate DQT table identifier")
                tables[table.table_id] = table
        elif marker in _SOF_MARKERS:
            if frame is not None:
                raise ValueError("multiple SOF markers are not supported")
            frame = _parse_sof_payload(marker, payload)

    if frame is None:
        raise ValueError("JPEG SOF marker was not found")
    if not tables:
        raise ValueError("JPEG DQT marker was not found")
    marker, precision, width, height, components = frame
    table_ids = set(tables)
    if any(
        component.quantization_table_id not in table_ids
        for component in components
    ):
        raise ValueError("SOF references a missing quantization table")
    return JPEGStructure(
        frame_marker=marker,
        precision_bits=precision,
        width=width,
        height=height,
        quantization_tables=tuple(tables[key] for key in sorted(tables)),
        components=components,
    )


def inspect_jpeg_syntax(jpeg_bytes: bytes) -> JPEGSyntaxSummary:
    """Inspect frame, scan, restart, JFIF, and Adobe marker properties."""
    structure = parse_jpeg_structure(jpeg_bytes)
    position = 2
    scan_count = 0
    restart_interval = 0
    restart_marker_count = 0
    jfif_present = False
    adobe_transform: int | None = None
    reached_eoi = False
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        marker_prefix = position
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker == 0xD9:
            reached_eoi = True
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if position + 2 > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment length")
        segment_length = int.from_bytes(
            jpeg_bytes[position : position + 2], "big"
        )
        if segment_length < 2:
            raise ValueError("invalid JPEG segment length")
        payload_start = position + 2
        payload_end = position + segment_length
        if payload_end > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment")
        payload = jpeg_bytes[payload_start:payload_end]
        position = payload_end
        if marker == 0xE0 and payload.startswith(b"JFIF\x00"):
            jfif_present = True
        elif marker == 0xEE and payload.startswith(b"Adobe"):
            if len(payload) < 12:
                raise ValueError("truncated Adobe APP14 segment")
            adobe_transform = payload[11]
        elif marker == 0xDD:
            if len(payload) != 2:
                raise ValueError("invalid DRI payload length")
            observed_interval = int.from_bytes(payload, "big")
            if restart_interval not in (0, observed_interval):
                raise ValueError("inconsistent restart intervals")
            restart_interval = observed_interval
        elif marker == 0xDA:
            scan_count += 1
            while position < len(jpeg_bytes):
                marker_prefix = jpeg_bytes.find(b"\xff", position)
                if marker_prefix < 0:
                    raise ValueError("entropy-coded scan has no closing marker")
                marker_position = marker_prefix + 1
                while (
                    marker_position < len(jpeg_bytes)
                    and jpeg_bytes[marker_position] == 0xFF
                ):
                    marker_position += 1
                if marker_position >= len(jpeg_bytes):
                    raise ValueError("truncated entropy-coded marker")
                entropy_marker = jpeg_bytes[marker_position]
                if entropy_marker == 0x00:
                    position = marker_position + 1
                    continue
                if 0xD0 <= entropy_marker <= 0xD7:
                    restart_marker_count += 1
                    position = marker_position + 1
                    continue
                position = marker_prefix
                break
        if position == marker_prefix:
            continue
    if not reached_eoi:
        raise ValueError("JPEG EOI marker was not found")
    if scan_count == 0:
        raise ValueError("JPEG SOS marker was not found")
    return JPEGSyntaxSummary(
        frame_marker=structure.frame_marker,
        scan_count=scan_count,
        restart_interval=restart_interval,
        restart_marker_count=restart_marker_count,
        jfif_present=jfif_present,
        adobe_transform=adobe_transform,
    )


def _parse_dqt_payload(payload: bytes) -> tuple[JPEGQuantizationTable, ...]:
    """Parse one DQT segment payload."""
    tables: list[JPEGQuantizationTable] = []
    position = 0
    while position < len(payload):
        info = payload[position]
        position += 1
        precision_code = info >> 4
        table_id = info & 0x0F
        if precision_code not in (0, 1):
            raise ValueError("unsupported DQT precision")
        if table_id > 3:
            raise ValueError("invalid DQT table identifier")
        precision_bits = 8 if precision_code == 0 else 16
        bytes_per_value = 1 if precision_bits == 8 else 2
        table_size = 64 * bytes_per_value
        if position + table_size > len(payload):
            raise ValueError("truncated DQT table")
        values = tuple(
            int.from_bytes(
                payload[
                    position + index * bytes_per_value :
                    position + (index + 1) * bytes_per_value
                ],
                "big",
            )
            for index in range(64)
        )
        position += table_size
        tables.append(
            JPEGQuantizationTable(
                table_id=table_id,
                precision_bits=precision_bits,
                values_zigzag=values,
            )
        )
    return tuple(tables)


def _parse_sof_payload(
    marker: int, payload: bytes
) -> tuple[int, int, int, int, tuple[JPEGComponent, ...]]:
    """Parse one start-of-frame payload."""
    if len(payload) < 6:
        raise ValueError("truncated SOF payload")
    precision = payload[0]
    height = int.from_bytes(payload[1:3], "big")
    width = int.from_bytes(payload[3:5], "big")
    component_count = payload[5]
    if width <= 0 or height <= 0 or component_count <= 0:
        raise ValueError("invalid SOF dimensions or component count")
    if len(payload) != 6 + 3 * component_count:
        raise ValueError("invalid SOF payload length")
    components = []
    for index in range(component_count):
        offset = 6 + 3 * index
        sampling = payload[offset + 1]
        horizontal = sampling >> 4
        vertical = sampling & 0x0F
        if horizontal == 0 or vertical == 0:
            raise ValueError("invalid SOF sampling factor")
        components.append(
            JPEGComponent(
                component_id=payload[offset],
                horizontal_sampling=horizontal,
                vertical_sampling=vertical,
                quantization_table_id=payload[offset + 2],
            )
        )
    return marker, precision, width, height, tuple(components)
