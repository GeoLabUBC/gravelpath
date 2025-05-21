import numpy as np
import pandas as pd
import glob
from openpyxl import load_workbook
import toml
from pathlib import Path


config_files = Path("configs_to_calibrate").rglob("*.toml")

# iterate over each config file
for cf in config_files:

    # load the config file
    c = toml.load(cf)

    #details of the experiment
    experiment_name = c['config']['run_name']
    discharge = c['config']['run_discharge']
    print(experiment_name)

    #enter the path to the directory containing the output of the lighttable code 
    light_table_directory =  c['paths']['results_path']

    #enter the path to the file containing sieved data 
    trap_grain_path = c['paths']['sieve_path']

    """
    Function calibrate is to calibrate the light table and sieving data
    inputs:
    light_table_results_directory: path to the experiment letter A,B,C,D, etc folder ending in with slash ex: '/Users/kyliegoguen/Downloads/work/calibrate_sample_code_kylie/Exp7/B/'
    trap_grain_path: direct path to the sieved data file ex: '/Users/kyliegoguen/Downloads/work/calibrate_sample_code_kylie/TRAP_GRAIN_EXP_7_B.csv'
    output: one .xlsx file in the same folder as the light table data per flow rate, containing two sheets
            one sheet (trap_comparison) compares the light table and sieved GSD data
            the other sheet (processed_data) provides the GSD for the minutes and seconds in the light table data
    """ 
    # Open the excel file workbook
    workbook = load_workbook('Blank_Lighttable_Calibrate.xlsx') # blank excel file
    
    # Define each of the worksheets
    trap_comparison_sheet = workbook['trap_comparison'] # light table vs. trap data
    processed_data_sheet = workbook['processed_data'] # time calibration

    #Read the No_Filter_gsd.csv
    light_table_data = pd.read_csv(f"{light_table_directory}/No_Filter_gsd.csv", delimiter=',')['fraction'].to_numpy()

    #Read the No_Filter_second_transport.csv
    transport_data = pd.read_csv(f"{light_table_directory}/No_Filter_second_transport.csv", delimiter=',')['Mass (g)'].to_numpy()

    # flow_rate = path[-21:-18]
        # # Accounts for experiments with F55.1/F55.2
        # if 'R' in flow_rate or 'F' in flow_rate:
        #     flow_rate = flow_rate
        # else:
        #     flow_rate = path[-23:-18]
        #     flow_rate = flow_rate.replace('.', '_')
    
    # Find the corresponding flow rate column to the flow rate light table data
    hydrograph_workbook = load_workbook(trap_grain_path, data_only=True)
    trap_data = hydrograph_workbook[discharge.replace(".", "_")]
    
    # Add the test flow rate
    processed_data_sheet['A1'] = experiment_name

    #convert the data from sieving datasheet to an array which is easier to manipulate
    trap_data_weights = []
    for cell in np.arange(23, 16, -1):
        trap_data_weights.append(trap_data[f'C{cell}'].value)
    for cell in np.arange(16, 8, -1):
        trap_data_weights.append(trap_data[f'B{cell}'].value)
    trap_data_weights = np.array(trap_data_weights)
    print(trap_data_weights)

    # Place the trap sieving data & light table grain size data into the calibration .xlsx file
    for ii, cell in enumerate(np.arange(15, 30, 1)):
        if cell > 16: #sieve data did not measure 0.7mm grain size so it has to be skipped
            trap_comparison_sheet[f'A{cell}'] = trap_data_weights[ii-1]
            trap_comparison_sheet[f'I{cell}'] = light_table_data[ii]
        elif cell == 16: #sieve data did not measure 0.7mm grain size so it has to be skipped
            trap_comparison_sheet[f'I{cell}'] = light_table_data[ii]
            continue
        elif cell == 15:
            trap_comparison_sheet[f'A{cell}'] = trap_data_weights[ii]
            trap_comparison_sheet[f'I{cell}'] = light_table_data[ii]

    # Place the light table transport data into the calibration .xlsx file
    for ii, mass in enumerate(transport_data):
        processed_data_sheet[f"C{8+ii}"] = mass

    # Place the sediment trap weight into the calibration .xlsx file
    processed_data_sheet['D3'] = trap_data["I2"].value

    # saves the calibration .xlsx file to the light table data path and prints the path it was saved to
    workbook.save(f'{light_table_directory}/Calibrated_{experiment_name}.xlsx') # Called Calibrate_{Test_Flow}
    print(f'Saved {experiment_name} to {light_table_directory}/Calibrate_{experiment_name}.xlsx')

    