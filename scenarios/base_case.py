import powergama
import powergama.scenarios
import pandas as pd
import numpy as np
import pathlib
import os

YEAR = 2020

def main(year):
    datapath_GridData = pathlib.Path().parent/f"data/nordic/data_{year}"
    file_storval_filling = pathlib.Path("data//nordic/data_storagevalues/profiles_storval_filling.csv")
    file_30y_profiles = pathlib.Path("data/nordic/data_timeseries/timeseries_profiles.csv.zip")
    # datapath_ProfileData = pathlib.Path().parent/f"data/nordic"
    # timerange = range(0, 24)
    date_start = "2020-01-01"
    date_end = "2020-02-01"
    sql_file = f"powergama_{year}.sqlite"

    data = powergama.GridData()
    data.readGridData(nodes=datapath_GridData / "node.csv",
                      ac_branches=datapath_GridData / "branch.csv",
                      dc_branches=datapath_GridData / "dcbranch.csv",
                      generators=datapath_GridData / "generator.csv",
                      consumers=datapath_GridData / "consumer.csv")


    # data.readProfileData(filename= datapath_ProfileData / "data_timeseries/timeseries_profiles.csv.zip",
    #                      storagevalue_filling=datapath_ProfileData / "data_storagevalues/profiles_storval_filling.csv",
    #                      storagevalue_time=datapath_ProfileData / "data_storagevalues/profiles_storval_filling_x.csv",
    #                      timerange=timerange,
    #                      timedelta=1.0)

    # Read profile data manually rather than using the data.readProfileData(...) method
    profiles_30y = pd.read_csv(file_30y_profiles, index_col=0, parse_dates=True)
    profiles_30y["const"] = 1
    data.profiles = profiles_30y[(profiles_30y.index >= date_start) & ((profiles_30y.index < date_end))].reset_index()
    data.storagevalue_time = data.profiles[["const"]]
    storval_filling = pd.read_csv(file_storval_filling)
    data.storagevalue_filling = storval_filling
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0  # hourly data

    num_hours = data.timerange[-1] - data.timerange[0]
    print(f'Simulation hours: {num_hours}')
    num_years = num_hours / (365.2425 * 24)
    print(f'Simulation years: {np.round(num_years, 3)}')

    # Filter offshore wind farms by year:
    data.generator = data.generator[~(data.generator["year"] > year)].reset_index(drop=True)

    # remove zero capacity generators:
    m_gen_hascap = data.generator["pmax"] > 0
    data.generator = data.generator[m_gen_hascap].reset_index(drop=True)


    lp = powergama.LpProblem(data)
    res = powergama.Results(data, sql_file, replace=True)
    lp.solve(res, solver="gurobi")

    print("System cost", sum(res.getSystemCost(timeMaxMin=[4, 6]).values()))
    print("Mean area price", sum(res.getAreaPricesAverage(timeMaxMin=[4, 6]).values()) / len(res.getAreaPricesAverage()))
    # res.plotEnergyMix(relative=True)

if __name__ == "__main__":
    main(YEAR)