# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'width': 81.0, 'length': 56.0, 'thickness': 9.0, 'holes': [{'x': 18.63, 'y': 14.56, 'diameter': 5.0}]}
OPENING='top'
SOURCE_SHA256='7fda60977b180b0e9a1570ed590f7cf1c3bfd7934eea0c85f17407a08b2128a6'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
