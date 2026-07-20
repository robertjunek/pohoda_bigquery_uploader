SELECT
  skz.IDS
  , skz.EAN
  , skz.Nazev
  , skz.StavZ
  , skz.MinLim
  , skl.ids AS sklad_zkratka
  , skl.SText AS sklad_nazev
  , typ.Stext as typ
  , zna.SText as znacka
  , kat.SText as kategorie
  , dru.SText as typ
  , bal.SText as velikost_baleni
  , skz.[VPrViditelnostBI] as viditelnost_bi
  , skz.VNakup
FROM SKz skz
LEFT JOIN sSklad skl ON skl.ID = skz.RefSklad
left join sVPULpol typ ON typ.ID = skz.RefVPrZasTyp
left join sVPULpol zna ON zna.ID = skz.RefVPrZasZnacka
left join sVPULpol kat ON kat.ID = skz.RefVPrZasKategor
left join sVPULpol dru ON dru.ID = skz.RefVPrZasDruh
left join sVPULpol bal ON bal.ID = skz.RefVPrDistBal
;