# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 7.0, 'kind': 'pocket', 'length': 17.0, 'opening': 'top', 'width': 25.0, 'x': 10.0, 'y': 12.0}, {'depth': 9.5, 'kind': 'pocket', 'length': 20.0, 'opening': 'top', 'width': 24.0, 'x': 76.0, 'y': 49.0}], 'length': 78.0, 'thickness': 24.0, 'width': 124.0}
SOURCE_SHA256='bade8f635c1e151dbdc65e593982e05f4e8891ab6938360330a3896183b75541'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
