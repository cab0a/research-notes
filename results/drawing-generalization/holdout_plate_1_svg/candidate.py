# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'width': 81.0, 'length': 56.0, 'thickness': 9.0, 'holes': [{'x': 18.63, 'y': 14.56, 'diameter': 5.0}]}
OPENING='top'
SOURCE_SHA256='4f527bce4f3833f5f8dd0004fb2943970469e396c07e8637f637f4baac1f8d2d'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
