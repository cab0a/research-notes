# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 115.0, 'length': 76.0, 'thickness': 23.0, 'features': [{'kind': 'pocket', 'x': 16.0, 'y': 12.0, 'width': 22.0, 'length': 18.0, 'depth': 6.5, 'opening': 'top'}, {'kind': 'hole', 'x': 90.0, 'y': 57.0, 'diameter': 9.0}]}
SOURCE_SHA256='1ce340f83f61c7709fd54d0bc009fdce681d683ba92a555996b18d46775d77a4'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
