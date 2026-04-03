DROP TABLE IF EXISTS staging_rxnconso;
CREATE TEMP TABLE staging_rxnconso (
    rxcui      text,
    lat        text,
    ts         text,
    lui        text,
    stt        text,
    sui        text,
    ispref     text,
    rxaui      text,
    saui       text,
    scui       text,
    sdui       text,
    sab        text,
    tty        text,
    code       text,
    str        text,
    srl        text,
    suppress   text,
    cvf        text,
    _end       text
);

COPY staging_rxnconso
FROM '/docker-entrypoint-initdb.d/RXNCONSO.RRF'
WITH (
    FORMAT csv,
    DELIMITER '|',
    QUOTE E'\b',
    ESCAPE E'\b'
);

INSERT INTO rxnconso (
    rxcui, lat, ts, lui, stt, sui, ispref, rxaui, saui, scui, sdui,
    sab, tty, code, str, srl, suppress, cvf
)
SELECT
    NULLIF(rxcui, ''),
    NULLIF(lat, ''),
    NULLIF(ts, ''),
    NULLIF(lui, ''),
    NULLIF(stt, ''),
    NULLIF(sui, ''),
    NULLIF(ispref, ''),
    NULLIF(rxaui, ''),
    NULLIF(saui, ''),
    NULLIF(scui, ''),
    NULLIF(sdui, ''),
    NULLIF(sab, ''),
    NULLIF(tty, ''),
    NULLIF(code, ''),
    NULLIF(str, ''),
    NULLIF(srl, ''),
    NULLIF(suppress, ''),
    NULLIF(cvf, '')
FROM staging_rxnconso;

DROP TABLE IF EXISTS staging_rxnrel;
CREATE TEMP TABLE staging_rxnrel (
    rxcui1     text,
    rxaui1     text,
    stype1     text,
    rel        text,
    rxcui2     text,
    rxaui2     text,
    stype2     text,
    rela       text,
    rui        text,
    srui       text,
    sab        text,
    sl         text,
    rg         text,
    dir        text,
    suppress   text,
    cvf        text,
    _end       text
);

COPY staging_rxnrel
FROM '/docker-entrypoint-initdb.d/RXNREL.RRF'
WITH (
    FORMAT csv,
    DELIMITER '|',
    QUOTE E'\b',
    ESCAPE E'\b'
);

INSERT INTO rxnrel (
    rxcui1, rxaui1, stype1, rel, rxcui2, rxaui2, stype2, rela,
    rui, srui, sab, sl, rg, dir, suppress, cvf
)
SELECT
    NULLIF(rxcui1, ''),
    NULLIF(rxaui1, ''),
    NULLIF(stype1, ''),
    NULLIF(rel, ''),
    NULLIF(rxcui2, ''),
    NULLIF(rxaui2, ''),
    NULLIF(stype2, ''),
    NULLIF(rela, ''),
    NULLIF(rui, ''),
    NULLIF(srui, ''),
    NULLIF(sab, ''),
    NULLIF(sl, ''),
    NULLIF(rg, ''),
    NULLIF(dir, ''),
    NULLIF(suppress, ''),
    NULLIF(cvf, '')
FROM staging_rxnrel;

DROP TABLE IF EXISTS staging_rxnsat;
CREATE TEMP TABLE staging_rxnsat (
    rxcui      text,
    lui        text,
    sui        text,
    rxaui      text,
    stype      text,
    code       text,
    atui       text,
    satui      text,
    atn        text,
    sab        text,
    atv        text,
    suppress   text,
    cvf        text,
    _end       text
);

COPY staging_rxnsat
FROM '/docker-entrypoint-initdb.d/RXNSAT.RRF'
WITH (
    FORMAT csv,
    DELIMITER '|',
    QUOTE E'\b',
    ESCAPE E'\b'
);

INSERT INTO rxnsat (
    rxcui, lui, sui, rxaui, stype, code, atui, satui, atn, sab, atv, suppress, cvf
)
SELECT
    NULLIF(rxcui, ''),
    NULLIF(lui, ''),
    NULLIF(sui, ''),
    NULLIF(rxaui, ''),
    NULLIF(stype, ''),
    NULLIF(code, ''),
    NULLIF(atui, ''),
    NULLIF(satui, ''),
    NULLIF(atn, ''),
    NULLIF(sab, ''),
    NULLIF(atv, ''),
    NULLIF(suppress, ''),
    NULLIF(cvf, '')
FROM staging_rxnsat;