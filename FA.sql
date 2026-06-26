SELECT
  CONCAT('FA-', r.ID) AS ID
  , 'faktury' AS Agenda
  , CASE
      RelTpFak
      WHEN 1 THEN 'faktura vydaná'
      WHEN 4 THEN 'zálohová faktura vydaná'
      WHEN 5 THEN 'pohledávky'
      WHEN 8 THEN 'opravný daňový doklad k faktuře vydané'
      WHEN 11 THEN 'faktura přijatá'
      WHEN 14 THEN 'zálohová faktura přijatá'
      WHEN 15 THEN 'závazky'
      WHEN 18 THEN 'opravný daňový doklad k faktuře přijate'
      ELSE '(jiné)'
    END AS TypDokladu
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
  , r.Prenes
  , r.KcJedn
  , r.Sleva
  , r.Kc
  , CASE
      WHEN ad.DIC IS NOT NULL THEN COALESCE(ad.Firma, ad.Firma2)
      ELSE NULL
    END Firma
  , ad.RefZeme
  , COALESCE(zem.IDS, 'CZ') AS KodZeme
FROM FA h
LEFT JOIN FApol r ON r.RefAg = h.ID
  --LEFT JOIN sSklad skl ON skl.ID = h.RefSklad
LEFT JOIN sStr str  ON str.ID = COALESCE(NULLIF(r.RefStr, 0), NULLIF(h.RefStr, 0))
LEFT JOIN sCin cin  ON cin.ID = COALESCE(NULLIF(r.RefCin, 0), NULLIF(h.RefCin, 0))
LEFT JOIN AD ad     ON ad.ID = h.RefAD
LEFT JOIN sZeme zem ON zem.ID = ad.RefZeme
WHERE COALESCE(h.DatSave, h.DatCreate ) >= GETDATE() - <DAYS_BACK>
-- AND r.Kod IS NOT NULL
;