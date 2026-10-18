# Enterprise exit: data issues to fix

Found in the extract of the Appointments configuration (staging copy of
production, 2026-10-18). Fix them on **production** (they matter today, and
the fixed data carries over to the Community server with the migration).

| # | Status | Issue | Impact | Fix |
|---|--------|-------|--------|-----|
| 1 | ☐ To do | "Call Center Tunis" is an answer of the "Rendez-vous pris à la place de" question, but no contact with that name has the "Call Center" tag. | Chosen 235 times in the last 12 months: those RDVs never got their "pris à la place de" partner, so the sales made from them miss their call-centre attribution (Call Center (Sale Owner), dashboards). **Affects production today.** | Create the contact "Call Center Tunis" with the tag "Call Center". Then, for the past RDVs, ask Claude for a script that fills the partner from the stored answers. |
| 2 | ☐ To do | The answer "Call Center Marrakech" does not match the contact "call marrakech" (the lookup is by exact name). | RDVs taken for Marrakech get no "pris à la place de" partner (same consequence as #1). | Rename the contact "call marrakech" to "Call Center Marrakech" (keep the "Call Center" tag). |
| 3 | ☐ To check | The user "Call Center Casa" is in the bookable staff of "Etude énergétique (par commercial)". | It is copied to the RDV type's commercials and will be offered as a "commercial" in the Community booking form for that type. | If it is a mistake, remove it from the staff of that appointment type in Appointments; the RDV type follows automatically (bgg_custom_dev_ee). |
| 4 | ☐ At go-live | Some of the biggest bookers are not in the "Call Center" group: alexandre@teleconcept.me (3,000 RDVs / 12 months), optimaenergypremium@gmail.com (2,209), hajar.moujahid@belgogroup.com (253), aysha.belwafa@digitrends.pro (239). | On the Community server, "Prise de RDV" is given automatically only to the "Call Center" and "Commercial" groups: these users would not see the booking form. | Either add them to the "Call Center" group now on production, or give them the "Prise de RDV (call center)" group by hand on the Community server after installing bgg_booking. |

## Notes

- Partners tagged "Call Center" today: Call Center Casa, Call Center
  Digitrends, Call Center Interne, Call Center Nogali, Call Center Parnasse,
  Call Center Tenerif, call marrakech.
- Users in the "Call Center" group today: Call Center Casa, Call Center
  Digitrends, Call Center Générique, Call Center Interne, Call Center
  Tenerif, call marrakech.
- RDV type commercials copied by the bgg_custom_dev 19.0.2.2.0 migration
  (checked on staging): 2 → 40, 4 → 37, 5 → 65, 10 → 65, 19 → 16, 20 → 15,
  46 → 63 (301 in total, identical to the Appointments staff).
