PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "django_site" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(50) NOT NULL, "domain" varchar(100) NOT NULL UNIQUE);
INSERT INTO django_site VALUES(1,'LottoBooM','lottoboom.com');
COMMIT;
