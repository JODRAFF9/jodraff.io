# =====================================================================
#  Système visuel — lu depuis shared/theme.json.
#
#  Mêmes valeurs que le dashboard Python, le front web et Angular :
#  palette catégorielle validée (bande de clarté, plancher de chroma,
#  séparation daltonisme sur les paires adjacentes), couleurs de statut
#  réservées, encre atténuée pour les axes.
# =====================================================================

SERIES     <- unlist(THEME$categorical$light)
SEQUENTIAL <- unlist(THEME$sequential$light)
STATUS     <- THEME$status
SURFACE    <- THEME$surface$light
DEPT_COLOR <- THEME$departments
FONT       <- THEME$typography$font_family

#' Couleur de la n-ième série — ordre FIXE, jamais recyclé par un filtre.
series_color <- function(index) SERIES[((index - 1) %% length(SERIES)) + 1]

#' Couleur d'un département.
dept_color <- function(code) {
  value <- DEPT_COLOR[[code]]
  if (is.null(value)) SURFACE$ink_muted else value
}

#' Statut de stock -> couleur, icône et libellé (jamais la couleur seule).
stock_badge <- function(status) {
  switch(status,
    "rupture" = list(color = STATUS$critical, icon = "⛔", label = "Rupture",
                     tint = "#fbeded", ink = "#8f2222"),
    "alerte"  = list(color = STATUS$serious,  icon = "▲", label = "À commander",
                     tint = "#fdefe8", ink = "#8a3d17"),
    "faible"  = list(color = STATUS$warning,  icon = "•", label = "Stock faible",
                     tint = "#fdf3e2", ink = "#7a5307"),
    list(color = STATUS$good, icon = "✓", label = "Disponible",
         tint = "#eaf7ea", ink = "#0a5d0a"))
}

#' Thème bslib de l'application.
erp_theme <- function() {
  bslib::bs_theme(
    version = 5,
    bg = SURFACE$card, fg = SURFACE$ink_primary,
    primary = SERIES[1], secondary = SURFACE$ink_secondary,
    success = STATUS$good, warning = STATUS$warning, danger = STATUS$critical,
    base_font = bslib::font_collection(
      bslib::font_google("Inter", local = FALSE, wght = c(400, 500, 600, 700)),
      "system-ui", "-apple-system", "Segoe UI", "sans-serif"),
    "body-bg" = SURFACE$page,
    "card-border-color" = SURFACE$border,
    "card-border-radius" = "10px",
    "font-size-base" = "0.875rem"
  )
}

#' Rampe séquentielle mono-teinte, du clair au foncé (n pas).
sequential_scale <- function(n) {
  usable <- SEQUENTIAL[4:length(SEQUENTIAL)]
  if (n <= 1) return(usable[length(usable) %/% 2])
  usable[round(seq(1, length(usable), length.out = n))]
}

#' Formatage monétaire compact : « 1,2 M FCFA ».
fmt_compact <- function(value, symbol = "") {
  if (length(value) == 0 || is.na(value[1])) return("—")
  value <- value[1]
  abs_value <- abs(value)
  sign <- if (value < 0) "-" else ""
  suffix <- if (nzchar(symbol)) paste0(" ", symbol) else ""
  out <- if (abs_value >= 1e9) sprintf("%s%s Md%s", sign, fr_num(abs_value / 1e9, 1), suffix)
    else if (abs_value >= 1e6) sprintf("%s%s M%s", sign, fr_num(abs_value / 1e6, 1), suffix)
    else if (abs_value >= 1e3) sprintf("%s%s k%s", sign, fr_num(abs_value / 1e3, 1), suffix)
    else sprintf("%s%s%s", sign, fr_num(abs_value, 0), suffix)
  out
}

#' Nombre au format français : espace pour les milliers, virgule décimale.
fr_num <- function(value, decimals = 0) {
  formatted <- formatC(value, format = "f", digits = decimals,
                       big.mark = " ", decimal.mark = ",")
  trimws(formatted)
}

#' Montant complet : « 1 234 567 FCFA ».
fmt_money <- function(value, symbol = "", decimals = 0) {
  if (length(value) == 0 || is.na(value[1])) return("—")
  paste0(fr_num(value[1], decimals), if (nzchar(symbol)) paste0(" ", symbol) else "")
}

#' « 2026-08 » -> « août 2026 ».
fr_period <- function(period) {
  months <- c("janv.", "févr.", "mars", "avr.", "mai", "juin",
              "juil.", "août", "sept.", "oct.", "nov.", "déc.")
  vapply(period, function(p) {
    if (is.na(p) || nchar(p) < 7) return(as.character(p))
    paste(months[as.integer(substr(p, 6, 7))], substr(p, 1, 4))
  }, "")
}

#' « 2026-08-16 » -> « 16/08 ».
fr_day <- function(day) {
  vapply(day, function(d) {
    if (is.na(d) || nchar(d) < 10) return(as.character(d))
    paste0(substr(d, 9, 10), "/", substr(d, 6, 7))
  }, "")
}

#' Évolution : flèche + valeur, la couleur ne porte jamais seule l'information.
delta_html <- function(pct) {
  if (is.null(pct) || is.na(pct)) {
    return(shiny::span(class = "delta flat", "— nouvelle période"))
  }
  flat <- abs(pct) < 0.05
  class <- if (flat) "flat" else if (pct > 0) "up" else "down"
  arrow <- if (flat) "→" else if (pct > 0) "↑" else "↓"
  shiny::span(class = paste("delta", class),
              sprintf("%s %s %%", arrow, fr_num(abs(pct), 1)))
}
