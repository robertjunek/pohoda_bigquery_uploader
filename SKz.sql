SELECT
  skz.IDS
  , skz.EAN
  , skz.Nazev
  , skz.StavZ
  , skz.MinLim
  , skl.ids AS sklad_zkratka
  , skl.SText AS sklad_nazev
FROM SKz skz
LEFT JOIN sSklad skl ON skl.ID = skz.RefSklad
;