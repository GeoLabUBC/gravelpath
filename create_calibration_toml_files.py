import toml 

'''
This is code to create mulitple toml files at once whilst changing the variables in the path and configs
'''

#base structure for the config file
calibration_config = {
    "config": {
        "run_name": "Exp{}", #{} is a placeholder for [Experiment #]_[Hydrograph Letter]_[Discharge]
        "run_discharge": "{}" #{} is a placeholder for the discharge
    },
    "paths": {
        "results_path": "D:/Sol/12m_HellySmith/LightTable/Output/Exp{}", #{} is a placed holder for [Experiment #]/[Hydrograh Letter]/[Discharge]/
        "sieve_path": "Z:/sol/12m_HellySmith/Transport_Data/Raw_Datasheets/EXP_{}_Trap.xlsx" #{} is a placeholder for [Experiment #]_[Hydrograph Letter]
    }
}

for experiment in ['9']: #['8', '10', '11', '12']:#['7']:#['1', '3', '4', '5', '6', '7']:
    for hydrograph in ['A', 'B', 'C', 'D']:#['E', 'F']:#['A', 'B', 'C', 'D']:
        for discharge in ['R55.1', 'R55.2', 'R60.1', 'R60.2', 'R66.1', 'R66.2', 'R73', 'R80', 'R88', 'F66', 'F55']: #['R55', 'R66', 'R88', 'F80', 'F73', 'F66.1', 'F66.2', 'F60.1', 'F60.2', 'F55.1', 'F55.2']: #['R55', 'R60', 'R66', 'R73', 'R80', 'R88', 'F80', 'F73', 'F66', 'F60', 'F55']:
            run_name = f"{experiment}_{hydrograph}_{discharge}"
            result_path = f"{experiment}/{hydrograph}/{discharge}/"
            sieve_path = f"{experiment}_{hydrograph}"

            config = {
            "config": {
                "run_name": calibration_config["config"]["run_name"].format(run_name),
                "run_discharge": calibration_config["config"]["run_discharge"].format(discharge)
                }, 
            "paths": {
                "results_path": calibration_config["paths"]["results_path"].format(result_path), 
                "sieve_path": calibration_config["paths"]["sieve_path"].format(sieve_path)
            }}

            file_name = f"configs_to_calibrate/Calib_Exp{experiment}_{hydrograph}_{discharge}.toml"
            with open(file_name, "w") as f:
                toml.dump(config, f)
            
            print(f"created {file_name}")