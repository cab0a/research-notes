# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 7.0, 'x': 13.0, 'y': 10.0}], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = '8decd41cd1fd7860d28051b9b60eedd2734e7c452e4097b16de6db9fc57bf329'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
