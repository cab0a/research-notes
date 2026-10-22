# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 7.0, 'x': 21.01, 'y': 14.3}, {'diameter': 7.8, 'x': 58.29, 'y': 37.95}, {'diameter': 5.0, 'x': 62.64, 'y': 14.85}], 'length': 55.0, 'thickness': 13.0, 'width': 92.0}
OPENING='top'
SOURCE_SHA256='efb67e318f8f239d125b00f57a1b1551b8d733c6c5407576eb2d0b977b421896'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
