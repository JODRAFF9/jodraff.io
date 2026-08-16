# =====================================================================
#  Constructeurs de graphiques (plotly).
#
#  Règles appliquées partout, comme dans les autres interfaces :
#    * un seul axe de valeurs, jamais deux échelles Y ;
#    * marques fines, extrémités arrondies, 2 px entre segments empilés ;
#    * légende dès deux séries, étiquettes directes sélectives ;
#    * grille discrète, axes en encre atténuée, survol actif.
# =====================================================================

#' Mise en forme commune (grille, axes, police, marges).
apply_layout <- function(p, height = 290, showlegend = FALSE, symbol = NULL, ...) {
  p <- plotly::layout(
    p,
    height = height,
    showlegend = showlegend,
    font = list(family = FONT, size = 13, color = SURFACE$ink_secondary),
    paper_bgcolor = SURFACE$chart,
    plot_bgcolor  = SURFACE$chart,
    margin = list(l = 60, r = 18, t = 18, b = 44),
    hovermode = "x unified",
    hoverlabel = list(font = list(family = FONT, size = 12), bgcolor = "#ffffff"),
    legend = list(orientation = "h", y = 1.08, x = 0,
                  font = list(size = 12, color = SURFACE$ink_secondary)),
    xaxis = list(showgrid = FALSE, zeroline = FALSE, linecolor = SURFACE$axis,
                 tickfont = list(color = SURFACE$ink_muted, size = 11),
                 type = "category", automargin = TRUE),
    yaxis = list(gridcolor = SURFACE$grid, zeroline = FALSE, showline = FALSE,
                 tickformat = "~s",
                 ticksuffix = if (is.null(symbol)) "" else paste0(" ", symbol),
                 tickfont = list(color = SURFACE$ink_muted, size = 11),
                 automargin = TRUE),
    ...
  )
  plotly::config(p, displayModeBar = FALSE, locale = "fr")
}

#' Courbe d'évolution. `series` est une liste nommée de vecteurs.
chart_line <- function(x, series, symbol = NULL, height = 280, fill = FALSE) {
  if (length(x) == 0) return(chart_empty("Aucune donnée sur la période."))
  p <- plotly::plot_ly()
  names_series <- names(series)
  for (i in seq_along(series)) {
    color <- series_color(i)
    p <- plotly::add_trace(
      p, x = x, y = series[[i]], name = names_series[i],
      type = "scatter", mode = "lines",
      line = list(color = color, width = 2, shape = "spline", smoothing = 0.4),
      fill = if (fill && length(series) == 1) "tozeroy" else "none",
      fillcolor = if (fill) paste0(color, "1A") else NULL,
      hovertemplate = paste0(names_series[i], " : %{y:,.0f}<extra></extra>"))
  }
  apply_layout(p, height, showlegend = length(series) > 1, symbol = symbol)
}

#' Barres verticales, une série, une couleur, pas de légende.
chart_bars <- function(labels, values, symbol = NULL, height = 280, color = NULL) {
  if (length(labels) == 0) return(chart_empty("Aucune donnée."))
  p <- plotly::plot_ly(
    x = labels, y = values, type = "bar",
    marker = list(color = color %||% series_color(1), cornerradius = 4),
    hovertemplate = "%{x}<br><b>%{y:,.0f}</b><extra></extra>")
  apply_layout(p, height, symbol = symbol, bargap = 0.3)
}

#' Barres groupées ou empilées, séries de MÊME unité.
chart_grouped <- function(x, series, symbol = NULL, height = 300, stacked = FALSE) {
  if (length(x) == 0) return(chart_empty("Aucune donnée."))
  p <- plotly::plot_ly()
  names_series <- names(series)
  for (i in seq_along(series)) {
    p <- plotly::add_trace(
      p, x = x, y = series[[i]], name = names_series[i], type = "bar",
      marker = list(color = series_color(i), cornerradius = 4,
                    line = if (stacked) list(width = 2, color = SURFACE$chart) else NULL),
      hovertemplate = paste0(names_series[i], " : %{y:,.0f}<extra></extra>"))
  }
  apply_layout(p, height, showlegend = TRUE, symbol = symbol,
               barmode = if (stacked) "stack" else "group",
               bargap = 0.28, bargroupgap = 0.08)
}

#' Répartition : barres horizontales triées, valeur et part affichées.
chart_share <- function(labels, values, symbol = "", height = NULL) {
  if (length(labels) == 0) return(chart_empty("Aucune donnée."))
  height <- height %||% max(200, 46 * length(labels) + 60)
  total <- sum(values)
  if (total == 0) total <- 1
  text <- sprintf("%s  ·  %d %%", vapply(values, fmt_compact, "", symbol),
                  round(values / total * 100))
  p <- plotly::plot_ly(
    x = values, y = factor(labels, levels = rev(labels)), type = "bar", orientation = "h",
    marker = list(color = vapply(seq_along(labels), series_color, ""), cornerradius = 4),
    text = text, textposition = "outside", cliponaxis = FALSE,
    textfont = list(size = 11.5, color = SURFACE$ink_secondary),
    hovertemplate = "%{y}<br><b>%{x:,.0f}</b><extra></extra>")
  p <- apply_layout(p, height, symbol = NULL)
  plotly::layout(
    p, hovermode = "closest",
    xaxis = list(showticklabels = FALSE, showgrid = FALSE, zeroline = FALSE,
                 range = c(0, max(values) * 1.9)),
    yaxis = list(showgrid = FALSE, automargin = TRUE, type = "category",
                 tickfont = list(color = SURFACE$ink_secondary, size = 12)))
}

#' Haltères : deux mesures de MÊME unité par catégorie.
chart_dumbbell <- function(labels, left, right, left_name, right_name,
                           symbol = NULL, height = NULL) {
  if (length(labels) == 0) return(chart_empty("Aucune donnée."))
  height <- height %||% max(220, 48 * length(labels) + 70)
  ordered <- factor(labels, levels = rev(labels))
  p <- plotly::plot_ly()
  for (i in seq_along(labels)) {
    p <- plotly::add_trace(
      p, x = c(left[i], right[i]), y = c(ordered[i], ordered[i]),
      type = "scatter", mode = "lines", showlegend = FALSE, hoverinfo = "skip",
      line = list(color = SURFACE$axis, width = 2))
  }
  p <- plotly::add_trace(
    p, x = left, y = ordered, type = "scatter", mode = "markers", name = left_name,
    marker = list(size = 11, color = series_color(1),
                  line = list(width = 2, color = SURFACE$chart)),
    hovertemplate = paste0(left_name, " · %{y}<br><b>%{x:,.0f}</b><extra></extra>"))
  p <- plotly::add_trace(
    p, x = right, y = ordered, type = "scatter", mode = "markers", name = right_name,
    marker = list(size = 11, color = series_color(3),
                  line = list(width = 2, color = SURFACE$chart)),
    hovertemplate = paste0(right_name, " · %{y}<br><b>%{x:,.0f}</b><extra></extra>"))
  p <- apply_layout(p, height, showlegend = TRUE, symbol = NULL)
  plotly::layout(
    p, hovermode = "closest",
    xaxis = list(tickformat = "~s", gridcolor = SURFACE$grid, zeroline = FALSE,
                 tickfont = list(color = SURFACE$ink_muted, size = 11)),
    yaxis = list(showgrid = FALSE, automargin = TRUE, type = "category",
                 tickfont = list(color = SURFACE$ink_secondary, size = 12)))
}

#' Carte de chaleur : magnitude continue, rampe mono-teinte.
chart_heatmap <- function(z, x, y, height = 300, unit = "") {
  scale <- sequential_scale(9)
  colorscale <- lapply(seq_along(scale), function(i) {
    list((i - 1) / (length(scale) - 1), scale[i])
  })
  p <- plotly::plot_ly(
    z = z, x = x, y = y, type = "heatmap", colorscale = colorscale,
    xgap = 2, ygap = 2,
    colorbar = list(thickness = 9, outlinewidth = 0, len = 0.85,
                    tickfont = list(size = 11, color = SURFACE$ink_muted)),
    hovertemplate = paste0("%{y} · %{x}<br><b>%{z:,.0f}", unit, "</b><extra></extra>"))
  p <- apply_layout(p, height)
  plotly::layout(p, hovermode = "closest",
                 yaxis = list(showgrid = FALSE, automargin = TRUE, type = "category",
                              tickfont = list(color = SURFACE$ink_muted, size = 11)))
}

#' Graphique vide (message centré), évite une zone blanche sans explication.
chart_empty <- function(message) {
  plotly::config(
    plotly::layout(
      plotly::plot_ly(type = "scatter", mode = "markers", x = numeric(0), y = numeric(0)),
      height = 200, paper_bgcolor = SURFACE$chart, plot_bgcolor = SURFACE$chart,
      xaxis = list(visible = FALSE), yaxis = list(visible = FALSE),
      annotations = list(list(text = message, showarrow = FALSE, xref = "paper",
                              yref = "paper", x = 0.5, y = 0.5,
                              font = list(size = 13, color = SURFACE$ink_muted)))),
    displayModeBar = FALSE)
}
