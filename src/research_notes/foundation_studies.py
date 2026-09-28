"""Registry and reproduction entry point for the v0.66-v0.80 foundation."""
from __future__ import annotations
import argparse
from importlib import import_module
from pathlib import Path


STUDIES=(
    (66,"semantic_pmi","advanced_geometry_studies"),
    (67,"spline_geometry","advanced_geometry_studies"),
    (68,"differential_geometry","advanced_geometry_studies"),
    (69,"intersection_analysis","advanced_geometry_studies"),
    (70,"repair_policies","advanced_geometry_studies"),
    (71,"mass_properties","engineering_studies"),
    (72,"proximity_analysis","engineering_studies"),
    (73,"spatial_workflow","engineering_studies"),
    (74,"independent_validation","engineering_studies"),
    (75,"change_pair_dataset","change_pair_dataset"),
    (76,"representation_learning","learning_studies"),
    (77,"candidate_ranking","learning_studies"),
    (78,"design_proposals","integration_studies"),
    (79,"conversational_proposals","integration_studies"),
    (80,"integrated_workflow","integration_studies"),
)


def run_study(name,output:Path,fixtures:Path,*,refresh=False):
    module=next((module for _,key,module in STUDIES if name==key),None)
    if module is None:raise ValueError("unknown foundation study")
    return getattr(import_module("research_notes."+module),"run_"+name)(output,fixtures,refresh=refresh)


def main(study=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("results"))
    parser.add_argument("--fixture-dir",type=Path,default=Path("fixtures")/(study.replace("_","-") if study else ""))
    parser.add_argument("--refresh-fixtures",action="store_true")
    args=parser.parse_args()
    for version,name,_ in STUDIES:
        if study is not None and name!=study:continue
        fixtures=args.fixture_dir if study else args.fixture_dir/name.replace("_","-")
        rows=run_study(name,args.output_dir,fixtures,refresh=args.refresh_fixtures)
        print(f"v0.{version}.0 {name}: {len(rows)} declared controls verified",flush=True)


if __name__=="__main__":main()
