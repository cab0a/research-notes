# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = 'e7db7f7cf785db0e20ba69eb5af955475d267709781e73d072874eda08522c9f'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
