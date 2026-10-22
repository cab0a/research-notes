# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 7.0, 'x': 13.0, 'y': 10.0}], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = 'cbd327a0062f1b781de9bcbd8e8a33626bfb1f183f5d615ce8c96b156e9ffe9f'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
