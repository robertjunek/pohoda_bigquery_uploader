SELECT
  skz.IDS
  , skz.EAN
  , skz.Nazev
  , skl.ids AS sklad_zkratka
  , skl.SText AS sklad_nazev
  , vc.VCislo as sarze
  , CAST(vc.DatExp AS DATE) AS datum_expirace
  , vc.StavVC as stav_vc
  , vc.StavOdlozVC as stav_odloz_vc
FROM SKz skz
LEFT JOIN sSklad skl ON skl.ID = skz.RefSklad
LEFT JOIN skzvc vc   ON vc.RefAg = skz.ID
WHERE vc.StavVC <> 0
AND vc.DatExp IS NOT NULL
;