import requests
import pandas as pd

def get_hydro_power_plants_in_operation():
    url = "https://api.nve.no/web/Powerplant/GetHydroPowerPlantsInOperation"

    # Make the request, return data
    response = requests.get(url)
    data = response.json()

    #convert to pandas dataframe, write to Excel
    df=pd.DataFrame(data)
    df.to_excel("hydro_power_plants_in_operation.xlsx", index=False)

if __name__ == '__main__':
    get_hydro_power_plants_in_operation()