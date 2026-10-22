# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 6.0, 'x': 19.63, 'y': 14.56}], 'length': 56.0, 'thickness': 11.0, 'width': 86.0}
OPENING='top'
SOURCE_SHA256='4f527bce4f3833f5f8dd0004fb2943970469e396c07e8637f637f4baac1f8d2d'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
