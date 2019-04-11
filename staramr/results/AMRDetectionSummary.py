from os import path

import pandas as pd
from pandas import DataFrame

from typing import List

import logging
logger = logging.getLogger("AMRDetectionSummary")

"""
Summarizes both ResFinder, PointFinder, and PlasmidFinder database results into a single table.
"""


class AMRDetectionSummary:
    SEPARATOR = ','
    FLOAT_DECIMALS = 2

    def __init__(self, files, resfinder_dataframe: DataFrame, pointfinder_dataframe=None, plasmidfinder_dataframe=None) -> None:
        """
        Constructs an object for summarizing AMR detection results.
        :param files: The list of genome files we have scanned against.
        :param resfinder_dataframe: The pd.DataFrame containing the ResFinder results.
        :param pointfinder_dataframe: The pd.DataFrame containing the PointFinder results.
        """
        self._names = [path.splitext(path.basename(x))[0] for x in files]
        self._resfinder_dataframe = resfinder_dataframe
        self._plasmidfinder_dataframe = plasmidfinder_dataframe

        if pointfinder_dataframe is not None:
            self._has_pointfinder = True
            self._pointfinder_dataframe = pointfinder_dataframe
        else:
            self._has_pointfinder = False

    def _compile_results(self, resistance_frame: DataFrame) -> DataFrame:
        df_summary = resistance_frame.sort_values(by=['Gene']).groupby(['Isolate ID']).aggregate(
            lambda x: {'Gene': (self.SEPARATOR + ' ').join(x['Gene'])})
        return df_summary[['Gene']]

    def _compile_plasmids(self, plasmid_frame: DataFrame) -> DataFrame:
        ds_summary = plasmid_frame.sort_values(by=['Gene']).groupby(['Isolate ID']).aggregate(
            lambda x: {'Gene': (self.SEPARATOR + ' ').join(x['Gene'])})

        ds_frame = ds_summary[['Gene']]

        plasmid_frame = ds_frame.rename(columns={'Gene': 'Plasmid Genes'})

        return plasmid_frame

    def _include_negatives(self, resistance_frame: DataFrame) -> DataFrame:
        result_names_set = set(resistance_frame.index.tolist())
        names_set = set(self._names)

        negative_names_set = names_set - result_names_set
        negative_entries = pd.DataFrame([[x, 'None'] for x in negative_names_set],
                                        columns=('Isolate ID', 'Gene')).set_index('Isolate ID')

        return resistance_frame.append(negative_entries, sort=True)

    def get_detailed_negative_columns(self):
        return ['Isolate ID', 'Gene', 'Start', 'End']

    def _include_detailed_negatives(self, resistance_frame: DataFrame, plasmid_frame: DataFrame=None) -> DataFrame:
        names_set = set(self._names)
        resfinder_names_set = set(resistance_frame.index.tolist())
        set_used = names_set

        negative_res_names_set = names_set - resfinder_names_set

        negative_entries = None
        negative_columns = self.get_detailed_negative_columns()

        if len(negative_res_names_set) != len(names_set) or resistance_frame.empty:
            negative_resistance_entries = pd.DataFrame([[x, 'None', 'Sensitive', '', ''] for x in negative_res_names_set],
                                                       columns=(negative_columns)).set_index('Isolate ID')
            negative_resistance_entries['Data Type']='Resistance'
            negative_entries = negative_resistance_entries

        if plasmid_frame is not None:
            plasmid_frame = self._compile_plasmids(plasmid_frame)
            plasmidfinder_names_set = set(plasmid_frame.index.tolist())
            negative_plasmid_names_set = names_set - plasmidfinder_names_set

            if not plasmid_frame.empty:
                set_used = negative_plasmid_names_set

        negative_plasmid_entries = pd.DataFrame([[x, 'None'] for x in set_used],
                                                columns=('Isolate ID', 'Gene')).set_index('Isolate ID')
        negative_plasmid_entries['Data Type']='Plasmid'

        if negative_entries is None:
            negative_entries = negative_plasmid_entries
        else:
            negative_entries = negative_entries.append(negative_plasmid_entries, sort=True)

        return resistance_frame.append(negative_entries, sort=True)

    def get_summary_empty_values(self):
        return {'Genotype': 'None'}

    def get_summary_resistance_columns(self):
        return ['Genotype', 'Plasmid Genes']

    def create_summary(self, include_negatives: bool=False) -> DataFrame:
        """
        Constructs a summary pd.DataFrame for all ResFinder/PointFinder/PlasmidFinder results.
        :param include_negatives: If True, include files with no ResFinder/PointFinder/PlasmidFinder results.
        :return: A pd.DataFrame summarizing the results.
        """
        resistance_frame = self._resfinder_dataframe
        plasmid_frame = self._plasmidfinder_dataframe

        if self._has_pointfinder:
            resistance_frame = resistance_frame.append(self._pointfinder_dataframe, sort=True)

        resistance_frame = self._compile_results(resistance_frame)

        if include_negatives:
            resistance_frame = self._include_negatives(resistance_frame)

        resistance_frame.rename(columns={'Gene': 'Genotype'}, inplace=True)

        fill_values = self.get_summary_empty_values()
        resistance_columns = self.get_summary_resistance_columns()

        if plasmid_frame is not None:
            plasmid_frame = self._compile_plasmids(plasmid_frame)

            if resistance_frame.empty:
                resistance_frame = resistance_frame.append(plasmid_frame)
                resistance_frame = resistance_frame.fillna(value=fill_values)
            else:
                resistance_frame = resistance_frame.merge(plasmid_frame, on='Isolate ID', how='left').fillna(value={'Plasmid Genes': 'None'})

            resistance_frame = resistance_frame.reindex(columns=resistance_columns)

        return resistance_frame.sort_index()

    def get_detailed_summary_columns(self):
        return ['Gene', '%Identity', '%Overlap', 'HSP Length/Total Length','Contig', 'Start', 'End', 'Accession', 'Data Type']

    def include_phenotype(self):
        return False

    def create_detailed_summary(self, include_negatives: bool=True) -> DataFrame:
        if self._resfinder_dataframe is None:
            resistance_frame = None
        else:
            resistance_frame = self._resfinder_dataframe.copy()
            resistance_frame['Data Type']='Resistance'
            resistance_frame = resistance_frame.round({'%Identity': self.FLOAT_DECIMALS, '%Overlap': self.FLOAT_DECIMALS})

        if self._plasmidfinder_dataframe is None:
            plasmid_frame = None
        else:
            plasmid_frame = self._plasmidfinder_dataframe.copy()

        column_names = self.get_detailed_summary_columns()

        if self._has_pointfinder:
            if self._pointfinder_dataframe is None:
                point_frame = None
            else:
                point_frame = self._pointfinder_dataframe.copy()
                point_frame['Data Type']='Resistance'
                point_frame = point_frame.round({'%Identity': self.FLOAT_DECIMALS, '%Overlap': self.FLOAT_DECIMALS})
                point_frame = point_frame.reindex(columns=column_names)

            if resistance_frame is not None:
                resistance_frame = resistance_frame.append(point_frame, sort=True)

        if include_negatives:
            if plasmid_frame is not None:
                plasmid_frame = plasmid_frame.reindex(columns=column_names)
                resistance_frame = self._include_detailed_negatives(resistance_frame, plasmid_frame)
            else:
                resistance_frame = self._include_detailed_negatives(resistance_frame)
            resistance_frame = resistance_frame.reindex(columns=column_names)

        if plasmid_frame is not None:
            plasmid_frame['Data Type']='Plasmid'

            if self.include_phenotype():
                plasmid_frame['Predicted Phenotype']=''
            
            plasmid_frame = plasmid_frame.round({'%Identity': self.FLOAT_DECIMALS, '%Overlap': self.FLOAT_DECIMALS})

            if resistance_frame is not None:
                resistance_frame = resistance_frame.append(plasmid_frame, sort=True)
                resistance_frame = resistance_frame.reindex(columns=column_names)
                resistance_frame = resistance_frame.sort_values(['Isolate ID', 'Data Type', 'Gene'])

        if resistance_frame is not None:
            resistance_frame = resistance_frame.fillna("")

        return resistance_frame
