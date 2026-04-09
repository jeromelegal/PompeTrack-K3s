FROM postgres:16

COPY 00_populate_postgresql_rxn.sh /docker-entrypoint-initdb.d/00_populate_postgresql_rxn.sh
COPY 01_Table_scripts_postgresql_rxn.sql /docker-entrypoint-initdb.d/01_Table_scripts_postgresql_rxn.sql
COPY 02_Load_scripts_postgresql_rxn_unix.sql /docker-entrypoint-initdb.d/02_Load_scripts_postgresql_rxn_unix.sql
COPY 03_Indexes_postgresql_rxn.sql /docker-entrypoint-initdb.d/03_Indexes_postgresql_rxn.sql

COPY RXNCONSO.RRF /docker-entrypoint-initdb.d/RXNCONSO.RRF
COPY RXNREL.RRF   /docker-entrypoint-initdb.d/RXNREL.RRF
COPY RXNSAT.RRF   /docker-entrypoint-initdb.d/RXNSAT.RRF

RUN chmod 755 /docker-entrypoint-initdb.d/00_populate_postgresql_rxn.sh