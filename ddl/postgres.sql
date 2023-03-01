CREATE TABLE MYTHIC_RECORD
(
    RECORD_ID VARCHAR(100) NOT NULL,
    SEASON NUMERIC(5) NOT NULL,
    PERIOD NUMERIC(10) NOT NULL,
    DUNGEON_ID NUMERIC(10) NOT NULL,
    DURATION NUMERIC(10) NOT NULL,
    COMPLETED_TIMESTAMP NUMERIC(20) NOT NULL,
    KEYSTONE_LEVEL NUMERIC(5) NOT NULL,
    KEYSTONE_UPGRADE NUMERIC(5) NOT NULL,
    JSON_TEXT TEXT NOT NULL,
    CONSTRAINT MYTHIC_RECOERD_PK PRIMARY KEY (RECORD_ID)
)
;
CREATE TABLE MYTHIC_RECORD_PLAYER
(
    RECORD_ID VARCHAR(100) NOT NULL,
    PLAYER_REALM VARCHAR(20) NOT NULL,
    PLAYER_NAME VARCHAR(100) NOT NULL,
    SPEC_ID NUMERIC(5) NOT NULL,
    CLASS_NAME VARCHAR(20) NOT NULL,
    SPEC_NAME VARCHAR(20) NOT NULL,
    ROLE_NAME VARCHAR(20) NOT NULL,
    CONSTRAINT MYTHIC_RECOERD_PLAYER_PK PRIMARY KEY (RECORD_ID,PLAYER_REALM,PLAYER_NAME)
)
;
CREATE TABLE MYTHIC_BOTUSER
(
    USER_ID VARCHAR(20) NOT NULL,
    WEB_SESSION_ID VARCHAR(100) NOT NULL,
    CONSTRAINT MYTHIC_BOTUSER_PK PRIMARY KEY (USER_ID)
)
;
CREATE TABLE MYTHIC_BOTUSER_PLAYER
(
    USER_ID VARCHAR(20) NOT NULL,
    PLAYER_REALM VARCHAR(20) NOT NULL,
    PLAYER_NAME VARCHAR(100) NOT NULL,
    CONSTRAINT MYTHIC_BOTUSER_PLAYER_PK PRIMARY KEY (USER_ID,PLAYER_REALM,PLAYER_NAME)
)
;
CREATE TABLE MYTHIC_BOTUSER_COMMENT
(
    USER_ID VARCHAR(20) NOT NULL,
    PLAYER_REALM VARCHAR(200) NOT NULL,
    PLAYER_NAME VARCHAR(100) NOT NULL,
    COMMENTS VARCHAR(1000) NOT NULL,
    CONSTRAINT MYTHIC_BOTUSER_COMMENT_PK PRIMARY KEY (USER_ID,PLAYER_REALM,PLAYER_NAME)
)
;
DROP TABLE MYTHIC_AUCTION;
CREATE TABLE MYTHIC_AUCTION
(
    AUCTION_ID NUMERIC(20) NOT NULL,
    REALM_ID NUMERIC(20) NOT NULL,
    ITEM_ID VARCHAR(200) NOT NULL,
    FIRST_SEEN_TS NUMERIC(20) NOT NULL,
    LAST_SEEN_TS NUMERIC(20) NOT NULL,
    JSON_TEXT TEXT NOT NULL,
    CONSTRAINT MYTHIC_AUCTION_PK PRIMARY KEY (AUCTION_ID)
)
;
DROP TABLE MYTHIC_ITEM;
CREATE TABLE MYTHIC_ITEM
(
    ITEM_ID VARCHAR(200) NOT NULL,
    JSON_TEXT TEXT NOT NULL,
    CONSTRAINT MYTHIC_ITEM_PK PRIMARY KEY (ITEM_ID)
)
;
