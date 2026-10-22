# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'width': 86.0, 'length': 51.0, 'thickness': 16.0, 'pocket_x': 11.0, 'pocket_y': 9.0, 'pocket_width': 20.0, 'pocket_length': 14.0, 'pocket_depth': 5.0}
OPENING='top'
SOURCE_SHA256='2d91390b26c60524e8768b537dc7424936efb3694d8fc5f7f8d3d5efdab0b483'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
