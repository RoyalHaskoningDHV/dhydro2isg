import os
import glob
import pandas as pd
import numpy as np
import csv
from dhydro2isg.config import ISG_DTYPES, ISG_COLUMNS, QMARKS_COLUMNS, ISG_HEADERROWS, ISG_RECORDLENGTH


def read_meta(ISG_file):
    ISG_read_table = pd.read_table(ISG_file)
    ISG = ISG_read_table.iloc[:, 0].str.split(',', expand=True)
    ISG.columns = ISG_COLUMNS
    for col in ISG_COLUMNS:
        if col in QMARKS_COLUMNS:
            ISG[col] = ISG[col].str.strip()
            ISG[col] = ISG[col].str.strip("\"")
    print("number of segments " + str(ISG.shape[0]))
    print("number of records "+ str((ISG.iloc[-1, 1])) + str((ISG.iloc[-1, 2])))
    return(ISG)


def read_isg_files(ISG_file: str):
    filename = os.path.splitext(os.path.basename(ISG_file))[0]
    path = os.path.dirname(ISG_file)
    list_of_fils = glob.glob(path + f'/{filename}*')
    dtype_list = ISG_DTYPES
    # load in all files
    array_dict = dict()
    for i, dt in dtype_list.items():
            file_r = [k for k in list_of_fils if k.endswith(i)]
            print("loading " + i + " from file " + file_r[0])
            array_dict[i] = (pd.DataFrame(np.fromfile(
                file_r[0],
                dtype=dt)).iloc[ISG_HEADERROWS[i]::])

            # delete b" before strings
            if any(array_dict[i].columns == "CNAME"):
                array_dict[i]["CNAME"] = array_dict[i]["CNAME"].str.decode(encoding='latin-1')
    return (array_dict)


def write_as_binary(df, filename, ext, savedir):
    dtype_list = ISG_DTYPES

    # add headerrows
    if ISG_HEADERROWS[ext] >= 1:
        df1 = pd.DataFrame([[0] * len(df.columns)]*ISG_HEADERROWS[ext], columns=df.columns)
        df1.iloc[0, 0] = ISG_RECORDLENGTH[ext]
        if ext in ["ISD1", "ISC1", "IST1", "ISQ1"]:
            df1.iloc[0, 3] = ""

        df = pd.concat([df1, df])

    x_records = df.to_records(index=False,
                              column_dtypes=dict(dtype_list[ext]))

    save_loc = savedir + "/" + filename + "." + ext
    x_records.tofile(save_loc, sep= "")
    return ext + "saved to" + save_loc


def write_as_text(df, filename, ext, savedir):
    from pathlib import Path
    
    # Ensure the output directory exists
    Path(savedir).mkdir(parents=True, exist_ok=True)

    if ext == "ISG":
        save_loc = savedir + "/" + filename + "." + ext
        file1 = open(save_loc, "w", newline='\r\n')
        file1.write(f'{" " * 9}{len(df)}{" " * 11}0\n')
        file1.close()
        # Add quotation marks to export
        for col in df.columns:
            if col in QMARKS_COLUMNS:
                df[col] = df[col].apply(lambda x: ' "' + x + '"')
        df.to_csv(save_loc, header=False, index=False, sep=',', mode='a', quoting=csv.QUOTE_NONE)
    else:
        save_loc = savedir + "/" + filename + "_" + ext + ".txt"
        df.to_csv(save_loc, header=True, index=False, sep='\t', mode='w', quoting=csv.QUOTE_NONNUMERIC)

    # print(ext + " saved to " + save_loc)