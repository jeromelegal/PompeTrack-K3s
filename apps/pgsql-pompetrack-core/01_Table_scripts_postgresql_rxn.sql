DROP TABLE IF EXISTS rxnconso;
CREATE TABLE rxnconso
(
   rxcui             varchar(8) NOT NULL,
   lat               varchar(3) DEFAULT 'ENG' NOT NULL,
   ts                varchar(1),
   lui               varchar(8),
   stt               varchar(3),
   sui               varchar(8),
   ispref            varchar(1),
   rxaui             varchar(8) NOT NULL,
   saui              varchar(50),
   scui              varchar(50),
   sdui              varchar(50),
   sab               varchar(20) NOT NULL,
   tty               varchar(20) NOT NULL,
   code              varchar(50) NOT NULL,
   str               varchar(3000) NOT NULL,
   srl               varchar(10),
   suppress          varchar(1),
   cvf               varchar(50)
);

DROP TABLE IF EXISTS rxnrel;
CREATE TABLE rxnrel
(
   rxcui1            varchar(8),
   rxaui1            varchar(8),
   stype1            varchar(50),
   rel               varchar(4),
   rxcui2            varchar(8),
   rxaui2            varchar(8),
   stype2            varchar(50),
   rela              varchar(100),
   rui               varchar(10),
   srui              varchar(50),
   sab               varchar(20) NOT NULL,
   sl                varchar(1000),
   rg                varchar(10),
   dir               varchar(1),
   suppress          varchar(1),
   cvf               varchar(50)
);

DROP TABLE IF EXISTS rxnsat;
CREATE TABLE rxnsat
(
   rxcui             varchar(8),
   lui               varchar(8),
   sui               varchar(8),
   rxaui             varchar(8),
   stype             varchar(50),
   code              varchar(50),
   atui              varchar(11),
   satui             varchar(50),
   atn               varchar(1000) NOT NULL,
   sab               varchar(20) NOT NULL,
   atv               varchar(4000),
   suppress          varchar(1),
   cvf               varchar(50)
);