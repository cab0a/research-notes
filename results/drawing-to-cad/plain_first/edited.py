# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = 'd79089402bbc75c18429157a92d42274f889509dab534f4c12fabeadbf2dc542'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
