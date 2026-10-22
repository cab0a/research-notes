# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 20.0, 'diameter2': 9.2, 'length1': 39.0, 'length2': 12.0}
OPENING='top'
SOURCE_SHA256='6bd12b3f2aeced72d6d73a571a269baa14b1416fb92936ac1d1911c0a22dcb88'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
