from pathlib import Path
import glob
import os
import logging
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)

for html_folder in glob.glob('data/raw_html/*file_num*'):
    folder_name = html_folder.split('/')[-1]
    done_dir = os.path.join("data", "raw_html", "done")
    if not os.path.exists(done_dir):
        os.mkdir(done_dir)
    logging.info(f'marking {folder_name} as done')
    Path(os.path.join(done_dir, folder_name)).touch()
