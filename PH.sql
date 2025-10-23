SELECT
  CONCAT('PH-', r.ID) AS ID
  , 'prodejky' AS Agenda
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
  , COALESCE(zem.IDS, 'CZ') AS KodZeme
  , h.Pozn
  , h.Pozn2
  , uh.IDS TypUhrady
  , k.IDS KodKasa
  , k.SText Kasa
  , h.Firma 
  , h.Jmeno 
  , h.SText AS HlavickaSText
FROM PH h
LEFT JOIN PHpol r ON r.RefAg = h.ID
LEFT JOIN sStr str   ON str.ID = COALESCE(NULLIF(r.RefStr, 0), NULLIF(h.RefStr, 0))
LEFT JOIN sCin cin   ON cin.ID = COALESCE(NULLIF(r.RefCin, 0), NULLIF(h.RefCin, 0))
LEFT JOIN AD ad      ON ad.ID = h.RefAD
LEFT JOIN sZeme zem  ON zem.ID = ad.RefZeme
LEFT JOIN sFormUh uh ON uh.ID = h.RelForUh
LEFT JOIN Kasa k ON k.ID = h.RefKasa 
WHERE r.Kod IS NOT NULL
AND COALESCE(h.DatSave, h.DatCreate ) >= GETDATE() - 14
;