# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 6.5, 'x': 18.5, 'y': 13.25}], 'length': 37.25, 'thickness': 8.5, 'width': 57.5}
SOURCE_SHA256 = '95ddf926fc6eef6c225d17cb545155c0ac55caaa36b649d069701ac4d7b73e10'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
