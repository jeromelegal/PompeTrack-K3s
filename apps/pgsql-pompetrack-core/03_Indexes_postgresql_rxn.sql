CREATE INDEX x_rxnconso_str   ON rxnconso(str);
CREATE INDEX x_rxnconso_rxcui ON rxnconso(rxcui);
CREATE INDEX x_rxnconso_tty   ON rxnconso(tty);
CREATE INDEX x_rxnconso_code  ON rxnconso(code);

CREATE INDEX x_rxnsat_rxcui   ON rxnsat(rxcui);
CREATE INDEX x_rxnsat_atv     ON rxnsat(atv);
CREATE INDEX x_rxnsat_atn     ON rxnsat(atn);

CREATE INDEX x_rxnrel_rxcui1  ON rxnrel(rxcui1);
CREATE INDEX x_rxnrel_rxcui2  ON rxnrel(rxcui2);
CREATE INDEX x_rxnrel_rela    ON rxnrel(rela);