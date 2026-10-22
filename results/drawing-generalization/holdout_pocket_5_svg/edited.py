# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 53.0, 'pocket_depth': 7.0, 'pocket_length': 16.0, 'pocket_width': 24.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 18.0, 'width': 78.0}
OPENING='top'
SOURCE_SHA256='0b157bf7ce04385c31ba6271daf7eca0193304a8093b91320cb406b8816fb790'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
