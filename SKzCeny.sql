SELECT
  skz.IDS
  , skz.EAN
  , skz.Nazev
  , skl.ids AS sklad_zkratka
  , skl.SText AS sklad_nazev
  , sc.IDS as typ_ceny
  , cn.ProdejC as prodejni_cena
  , cn.Rabat as rabat
FROM SKz skz
LEFT JOIN sSklad skl ON skl.ID = skz.RefSklad
LEFT JOIN SKzCn cn   ON cn.RefAg = skz.ID
left join SkCeny sc ON sc.ID = cn.RefSkCeny 
where skz.VPrViditelnostBI = 1
;