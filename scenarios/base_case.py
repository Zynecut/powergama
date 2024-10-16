import powergama
import powergama.scenarios
import pandas as pd
import pathlib
import os

YEAR = 2040

def main(year):
    datapath = pathlib.Path(f"scenarios/data/nordic/data_{year}")
    data = powergama.GridData()
    data.readGridData(nodes=datapath / "nodes.csv",
                      ac_branches=datapath / "branches.csv",
                      dc_branches=datapath / "dcbranches.csv",
                      generators=datapath / "generators.csv",
                      consumers=datapath / "consumers.csv")

    data.readProfileData(filename="",
                         storagevalue_filling="",
                         storagevalue_time="",
                         timerange="",
                         timedelta="")






if __name__ == "__main__":
    main(YEAR)