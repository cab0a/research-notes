# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'width': 40.0, 'length': 30.0, 'thickness': 8.0, 'holes': []}
SOURCE_SHA256 = '5f1cbfdf14a0d974286ac4e5f6ef4e17458ce75deff64af535fd26f3eb50208a'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)
