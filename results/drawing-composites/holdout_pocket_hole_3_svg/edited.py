# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 7.0, 'kind': 'pocket', 'length': 18.0, 'opening': 'top', 'width': 23.0, 'x': 16.0, 'y': 12.0}, {'diameter': 9.5, 'kind': 'hole', 'x': 90.5, 'y': 57.0}], 'length': 76.0, 'thickness': 24.0, 'width': 119.0}
SOURCE_SHA256='1ce340f83f61c7709fd54d0bc009fdce681d683ba92a555996b18d46775d77a4'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
