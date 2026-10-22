# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 120.0, 'length': 78.0, 'thickness': 23.0, 'features': [{'kind': 'pocket', 'x': 10.0, 'y': 12.0, 'width': 24.0, 'length': 17.0, 'depth': 6.5, 'opening': 'top'}, {'kind': 'pocket', 'x': 76.0, 'y': 49.0, 'width': 24.0, 'length': 20.0, 'depth': 9.5, 'opening': 'top'}]}
SOURCE_SHA256='bade8f635c1e151dbdc65e593982e05f4e8891ab6938360330a3896183b75541'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
