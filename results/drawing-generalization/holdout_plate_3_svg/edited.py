# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 7.0, 'x': 21.01, 'y': 14.3}, {'diameter': 7.8, 'x': 58.29, 'y': 37.95}, {'diameter': 5.0, 'x': 62.64, 'y': 14.85}], 'length': 55.0, 'thickness': 13.0, 'width': 92.0}
OPENING='top'
SOURCE_SHA256='d9746e019f405404bc5db17da0caae275a9fdc2d7127967bb179278ed04d32bc'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
