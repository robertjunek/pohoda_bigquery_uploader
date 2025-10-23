SELECT
  CONCAT('PH-', r.ID) AS ID
  , 'prodejky' as Agenda
  , h.Cislo AS CisloDokladu
  , CAST(h.Datum AS DATE) AS Datum
  , COALESCE(NULLIF(r.RefCin, 0), NULLIF(h.RefCin, 0)) RefCin
  , cin.IDS AS KodCinnost
  , cin.Stext AS Cinnost
  , COALESCE(NULLIF(r.RefStr, 0), NULLIF(h.RefStr, 0)) RefStr
  , str.IDS KodStredisko
  , str.SText Stredisko
  , h.RelStorn
  , h.RefAD
  , r.Kod
  , r.SText
  , r.VCislo
  , r.Mnozstvi
  , r.KcJedn
  , r.Sleva
  , r.Kc
  , CASE
    WHEN ad.DIC IS NOT NULL THEN COALESCE(ad.Firma, ad.Firma2)
    ELSE NULL
  END Firma
  , ad.RefZeme
  , COALESCE(zem.IDS, 'CZ') as KodZeme
FROM PH h
LEFT JOIN PHpol r  ON r.RefAg = h.ID
--LEFT JOIN sSklad skl ON skl.ID = h.RefSklad
LEFT JOIN sStr str   ON str.ID = COALESCE(NULLIF(r.RefStr, 0), NULLIF(h.RefStr, 0))
LEFT JOIN sCin cin   ON cin.ID = COALESCE(NULLIF(r.RefCin, 0), NULLIF(h.RefCin, 0))
LEFT JOIN AD ad      ON ad.ID = h.RefAD
LEFT JOIN sZeme zem  ON zem.ID = ad.RefZeme
WHERE r.Kod IS NOT NULL
AND COALESCE(h.DatSave, h.DatCreate ) >= GETDATE() - 14
;