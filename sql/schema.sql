CREATE TABLE IF NOT EXISTS applications (

    SK_ID_CURR              INTEGER  PRIMARY KEY,

    TARGET                  INTEGER,          

   
    NAME_CONTRACT_TYPE      TEXT, 
    CODE_GENDER             TEXT, 
    FLAG_OWN_CAR            TEXT, 
    FLAG_OWN_REALTY         TEXT, 
    CNT_CHILDREN            INTEGER,
    CNT_FAM_MEMBERS         REAL,

   
    AMT_INCOME_TOTAL        REAL,
    AMT_CREDIT              REAL,
    AMT_ANNUITY             REAL,
    AMT_GOODS_PRICE         REAL,


    NAME_TYPE_SUITE         TEXT,
    NAME_INCOME_TYPE        TEXT,
    NAME_EDUCATION_TYPE     TEXT,
    NAME_FAMILY_STATUS      TEXT,
    NAME_HOUSING_TYPE       TEXT,
    OCCUPATION_TYPE         TEXT,
    WEEKDAY_APPR_PROCESS_START TEXT,
    ORGANIZATION_TYPE       TEXT,


    DAYS_BIRTH              INTEGER,        
    DAYS_EMPLOYED           INTEGER,          
    DAYS_REGISTRATION       REAL,
    DAYS_ID_PUBLISH         INTEGER,


    EXT_SOURCE_1            REAL,           
    EXT_SOURCE_2            REAL,
    EXT_SOURCE_3            REAL,


    REGION_POPULATION_RELATIVE REAL,


    BUREAU_LOAN_COUNT       INTEGER,
    BUREAU_ACTIVE_LOANS     INTEGER,
    BUREAU_AVG_DAYS_CREDIT  REAL,
    BUREAU_TOTAL_CREDIT_SUM REAL,
    BUREAU_TOTAL_OVERDUE    REAL,


    PREV_APP_COUNT          INTEGER,
    PREV_APPROVED_COUNT     INTEGER,
    PREV_REFUSED_COUNT      INTEGER,
    PREV_AVG_AMT_APPLICATION REAL,
    PREV_AVG_AMT_CREDIT     REAL,


    RISK_BAND               TEXT,            
    RISK_SCORE              REAL              

);


CREATE INDEX IF NOT EXISTS idx_target        ON applications(TARGET);
CREATE INDEX IF NOT EXISTS idx_gender        ON applications(CODE_GENDER);
CREATE INDEX IF NOT EXISTS idx_income_type   ON applications(NAME_INCOME_TYPE);
CREATE INDEX IF NOT EXISTS idx_education     ON applications(NAME_EDUCATION_TYPE);
CREATE INDEX IF NOT EXISTS idx_risk_band     ON applications(RISK_BAND);
CREATE INDEX IF NOT EXISTS idx_occupation    ON applications(OCCUPATION_TYPE);
CREATE INDEX IF NOT EXISTS idx_org_type      ON applications(ORGANIZATION_TYPE);
CREATE INDEX IF NOT EXISTS idx_ext2          ON applications(EXT_SOURCE_2);
