# Risk pages: design preview

Invented example showing what the free pages can hold. Real reports use report_XX/pages.md.

# page
kicker: Stress test
title: If 2022 happened again
byline: Risk team [authors]
sources: Illustrative. Shock: each position's actual GBP return from 3 Jan to 30 Jun 2022, applied to today's book (historical replay). Not a forecast or a maximum loss. S01 Bloomberg daily prices.

We replay the first half of 2022, when UK and US 10-year yields rose about 150bp and long-duration growth stocks fell hardest, through today's holdings. It is the scenario our factor profile is most exposed to: long quality and momentum, short value.

::: tiles
Fund impact | −4.6% NAV | −£138k on today's book
Worst team | TMT | −1.4% of fund NAV
Positions covered | 38 / 38 | 2 proxied (IPO after 2022)
Worst single position | −0.9% | TMT3 XX, long
:::

::: cols 3:2
![Loss by team | % of fund NAV, H1 2022 replay](demo_stress_by_team.svg)
|||
### Why TMT and Materials lead the loss
The TMT longs are high-multiple software and semis that fell 30–45% in the replay; the shorts were cut back in October, so less offsets the longs.

Materials loses on the other side: its shorts are miners that **rose** in 2022 as commodities rallied.

Energy & Utilities is the only team that gains.
:::

## What the replay does not capture
- Borrow costs and recalls on the shorts during the squeeze: the simulator does not charge them.
- Two holdings listed after 2022 and use their sector index as a proxy.
- Positions are held fixed for six months; in practice PMs would trade.

> !
> **Recommendation to TMT and Materials**
> Review whether TMT's duration exposure is intended: the team's longs account for 31% of the replay loss but 16% of gross. Materials: confirm the miner shorts are a deliberate commodity view, not a hedge. Responses by 14 December; logged as RA-07 and RA-08.

# page
kicker: Thematic
title: One trade in three teams' clothing
byline: Risk team [authors]
sources: Illustrative. Correlation: 60-day rolling average pairwise correlation of daily GBP returns. S01 Bloomberg daily prices, to 30 Nov 2026.

![Crowding in the AI-capex theme | Average pairwise correlation, 60-day rolling](demo_crowding.svg)

::: text2
Three teams hold names whose story is AI data-centre spending: TMT through semis, Industrials through power equipment, and Energy & Utilities through grid operators. Each is inside its own limits. Together they make up 19% of gross, and since September they have traded more and more like one position.

Sector labels hide this. On the dashboard each team looks diversified; the correlation says they are not. On a day when the capex story is questioned, for example a hyperscaler cutting guidance, all three teams fall together and the fund-level loss is about twice what the team views suggest.

This is not a call to sell. The theme may be right. The question is whether the fund wants one bet of this size and whether anyone owns it as a single position.
:::

| Theme exposure | Long % NAV | Short % NAV | Share of VaR | Teams |
|---|---|---|---|---|
| AI-capex | 24.1% | 2.3% | 34% | TMT, Industrials, Energy & Utilities |
| UK consumer | 9.8% | 6.2% | 8% | Consumer, Financials |
| Rate-sensitive defensives | 7.5% | 11.0% | 6% | Healthcare, Energy & Utilities |

::: cols
> **What would change our view**
> Correlation falling back below 0.4 for a month, or the three teams' names diverging on earnings.
|||
> **Question for the CIO**
> Should there be a cap on any single theme across teams, like the 30% subsector cap in the strategy?
:::

Note: themes are tagged by the Risk team from company disclosures; tagging is judgement, not a data feed.
