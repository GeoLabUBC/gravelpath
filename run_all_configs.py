import toml
from pathlib import Path
from lighttable.image_looper import ImageLooper
from lighttable.particle_looper_filters import Particle_Filters
from lighttable.particle_extractor import Particle_Extractor

#set up logging
import logging
from datetime import datetime

#setting up multiprocessing
import numpy as np
import multiprocessing as mp

def chunk(images, numImagesPerProc):
    '''
    Break image paths into seperate chunks that can be served to each process
    '''
    for i in range(0, len(images), numImagesPerProc):
        yield images[i : i  + numImagesPerProc]

if __name__ == '__main__':

    #Ensure multprocessing works the same on all systems
    mp.set_start_method("spawn")

    #Get the maximum number of cpu cores / threads to run the work on
    procs = mp.cpu_count()

    config_files = Path("configs_to_run").rglob("*.toml")

    # iterate over each config file
    for cf in config_files:
        # load the config file
        c = toml.load(cf)

        # Output directory, create if it doesn't exist
        Path(c["output"]["path"]).mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(__name__)

        #set up logging, will be one file per execution
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(
                    Path(__file__).parent / "logs" / f"{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log"),],)   


        #chunk the images into seperate payloads which can be passed to each processor
        images = list(Path(c['images']['path']).rglob("*.tif"))
        images = sorted(images)
        numImagesPerProc = len(images) / float(procs)
        numImagesPerProc = int(np.ceil(numImagesPerProc))
        chunkedPaths = list(chunk(images, numImagesPerProc))
        payloads = []

        for i, images in enumerate(chunkedPaths):
            data = {
                "id": i,
                "image_paths": images,}
            payloads.append(data)

        # run image processing
        Looper = ImageLooper(c)
        Looper.run(payloads)


        #TODO Comment this out if not using an analyser to try and link particles
        # # # # connect particles
        # Analyser = Particle_Filters(c)
        # Analyser.run()

        # extract the data
        Extractor = Particle_Extractor(c)
        Extractor.run()

        print(f"Finished processing {cf.name}")