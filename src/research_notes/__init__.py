"""Small, reproducible utilities used by the published research notes."""

from research_notes.blur_models import apply_psf, disk_psf, linear_motion_psf
from research_notes.blur_metrics import (
    laplacian_variance,
    sliding_metric_map,
    tenengrad_energy,
    tiled_metric_map,
)
from research_notes.photometric import (
    gamma_transform,
    jpeg_encode_decode,
    linear_intensity_transform,
    minmax_normalize,
    repeated_jpeg_round_trip,
    to_grayscale,
)
from research_notes.jpeg_codec import (
    JPEGComponent,
    JPEGQuantizationTable,
    JPEGStructure,
    JPEGSyntaxSummary,
    decode_jpeg_ffmpeg,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_cmyk_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    ffmpeg_build_information,
    inspect_jpeg_syntax,
    parse_jpeg_structure,
)
from research_notes.jpeg_contracts import (
    PixelDifference,
    classify_decoded_pixel_contract,
    compare_decoded_pixels,
    pixel_array_sha256,
)
from research_notes.preprocessing import (
    gaussian_denoise,
    jpeg_round_trip,
    resize_round_trip,
    unsharp_mask,
)

__all__ = [
    "apply_psf",
    "disk_psf",
    "gaussian_denoise",
    "gamma_transform",
    "jpeg_encode_decode",
    "JPEGComponent",
    "JPEGQuantizationTable",
    "JPEGStructure",
    "JPEGSyntaxSummary",
    "PixelDifference",
    "classify_decoded_pixel_contract",
    "compare_decoded_pixels",
    "decode_jpeg_opencv",
    "decode_jpeg_pillow",
    "decode_jpeg_ffmpeg",
    "encode_jpeg_cmyk_pillow",
    "encode_jpeg_opencv",
    "encode_jpeg_pillow",
    "ffmpeg_build_information",
    "inspect_jpeg_syntax",
    "jpeg_round_trip",
    "laplacian_variance",
    "linear_intensity_transform",
    "linear_motion_psf",
    "minmax_normalize",
    "parse_jpeg_structure",
    "pixel_array_sha256",
    "repeated_jpeg_round_trip",
    "resize_round_trip",
    "sliding_metric_map",
    "tenengrad_energy",
    "tiled_metric_map",
    "to_grayscale",
    "unsharp_mask",
]
