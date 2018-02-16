from Bio.Blast import NCBIXML
from Bio.Blast.Applications import NcbiblastnCommandline
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile

import logging

logger = logging.getLogger('BlastHandler')

class BlastHandler:

    def __init__(self, resfinder_database, pointfinder_database = None, threads = 1):
        self._resfinder_database = resfinder_database
        self._threads = threads

        if (pointfinder_database == None):
            self._pointfinder_configured = False
        else:
            self._pointfinder_database = pointfinder_database
            self._pointfinder_configured = True

        self._thread_pool_executor = None
        self.reset()

    def reset(self):
        if self._thread_pool_executor is not None:
            self._thread_pool_executor.shutdown()
        self._thread_pool_executor = ThreadPoolExecutor(max_workers=self._threads)
        self._resfinder_blast_map = {}
        self._pointfinder_blast_map = {}
        self._pointfinder_future_blasts = []
        self._resfinder_future_blasts = []
        self._temp_dirs = []

    def run_blasts(self, files):
        database_names_resfinder = self._resfinder_database.get_database_names()
        logger.info("Resfinder Databases: " + str(database_names_resfinder))

        if self.is_pointfinder_configured():
            database_names_pointfinder = self._pointfinder_database.get_database_names()
            logger.debug("Pointfinder Databases: " + str(database_names_pointfinder))

        for file in files:
            logger.info("Scheduling blast for " + file)
            self._schedule_resfinder_blast(file, database_names_resfinder)
            if self.is_pointfinder_configured():
                self._schedule_pointfinder_blast(file, database_names_pointfinder)

    def _schedule_resfinder_blast(self, file, database_names):
        for database_name in database_names:
            database = self._resfinder_database.get_path(database_name)
            file_name = os.path.basename(file)
            dir = tempfile.TemporaryDirectory()

            # Forces temporary directories to not be cleaned up until program is finished
            self._temp_dirs.append(dir)

            blast_out = os.path.join(dir.name, file_name + ".blast.xml")
            self._resfinder_blast_map.setdefault(file_name, {})[database_name] = blast_out

            future_blast = self._thread_pool_executor.submit(self._launch_blast, file, database, blast_out)
            self._resfinder_future_blasts.append(future_blast)

    def _schedule_pointfinder_blast(self, file, database_names):
        for database_name in database_names:
            database = self._pointfinder_database.get_path(database_name)
            file_name = os.path.basename(file)
            dir = tempfile.TemporaryDirectory()

            # Forces temporary directories to not be cleaned up until program is finished
            self._temp_dirs.append(dir)

            blast_out = os.path.join(dir.name, file_name + ".blast.xml")
            self._pointfinder_blast_map.setdefault(file_name, {})[database_name] = blast_out

            future_blast = self._thread_pool_executor.submit(self._launch_blast, file, database, blast_out)
            self._pointfinder_future_blasts.append(future_blast)

    def is_pointfinder_configured(self):
        return self._pointfinder_configured

    def get_resfinder_outputs(self):
        # Forces any exceptions to be thrown if error with blasts
        for future_blast in self._resfinder_future_blasts:
            future_blast.result()
        return self._resfinder_blast_map

    def get_pointfinder_outputs(self):
        if (self.is_pointfinder_configured()):
            # Forces any exceptions to be thrown if error with blasts
            for future_blast in self._pointfinder_future_blasts:
                future_blast.result()
            return self._pointfinder_blast_map
        else:
            raise Exception("Error, pointfinder has not been configured")

    def _launch_blast(self, query, db, output):
        blastn_command = NcbiblastnCommandline(query=query, db=db, evalue=0.001, outfmt=5, out=output)
        logger.debug(blastn_command)
        stdout, stderr = blastn_command()
        if stderr:
            raise Exception("error with [" + str(blastn_command) + "], stderr=" + stderr)