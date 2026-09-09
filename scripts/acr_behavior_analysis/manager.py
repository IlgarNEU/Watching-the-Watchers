#TODO: CHANGE CSV PATH
#TODO: CHANGE INPUT PATH
import os
import subprocess
import sys
import pandas as pd

def run_dns_name_analysis():
    csv_path = "/home/mammadovi/75pdomainlist/samsung/full_list.csv"  #todo: CSV PATH CHANGE
    df = pd.read_csv(csv_path)
    for idx, row in df.iterrows():
        run_for_row(idx+1, row)
    
    
    
def run_for_row(index, row):
    script_path = "/home/mammadovi/automatic_acr_analysis_codes/analysis_codes/acrfileCreation.py"
    domain_name = str(row["domain"])
    #domain_name = "alphonso.tv"
    input_path = "/home/mammadovi/automatic_acr_merged_csvs/samsung/" #TODO: CHANEG INPUT PATH
    subprocess.run(['../venv/bin/python', script_path,  input_path, domain_name], check=True)

if __name__ == "__main__":
    run_dns_name_analysis()