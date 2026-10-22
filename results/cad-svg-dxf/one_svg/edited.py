# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 7.0, 'x': 13.0, 'y': 10.0}], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = '712407c058ea33a26f2f1966fa5885cc732870886aa742bffeac205ee548ec5e'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
