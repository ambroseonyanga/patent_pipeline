import zipfile, pandas as pd

zip_path = r"c:\Users\Ambrose\OneDrive\Desktop\patent_pipeline\data\raw\g_patent_abstract.tsv.zip"

with zipfile.ZipFile(zip_path) as z:
    print("Files in zip:", z.namelist())
    with z.open(z.namelist()[0]) as f:
        cols = pd.read_csv(f, sep="\t", nrows=0).columns.tolist()
        print("Columns:", cols)