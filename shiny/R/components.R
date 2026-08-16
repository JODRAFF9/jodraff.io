# =====================================================================
#  Briques d'interface réutilisées par tous les modules.
# =====================================================================

#' Tuile d'indicateur : un chiffre qui se lit sans graphique.
kpi_tile <- function(label, value, foot = NULL, accent = SURFACE$ink_muted) {
  div(
    class = "card kpi",
    div(class = "kpi-accent", style = paste0("background:", accent)),
    div(class = "kpi-label", label),
    div(class = "kpi-value", value),
    div(class = "kpi-foot", foot)
  )
}

#' Carte de contenu : titre, note explicative, corps.
erp_card <- function(title, ..., note = NULL, class = NULL) {
  div(
    class = paste("card", class),
    tags$p(class = "card-title", title),
    if (!is.null(note)) tags$p(class = "card-note", note) else div(style = "height:8px"),
    ...
  )
}

#' Pastille d'état de stock : couleur + icône + libellé.
badge <- function(status) {
  spec <- stock_badge(status)
  span(class = "badge",
       style = sprintf("background:%s;color:%s", spec$tint, spec$ink),
       span(class = "badge-dot", style = paste0("background:", spec$color)),
       paste(spec$icon, spec$label))
}

#' En-tête de page.
page_header <- function(title, subtitle) {
  div(class = "page-head",
      h1(class = "page-title", title),
      tags$p(class = "page-sub", subtitle))
}

#' Grille de tuiles.
kpi_grid <- function(...) div(class = "grid grid-kpi", ...)

#' Tableau interactif — c'est aussi la « vue table » des graphiques.
#'
#' @param columns liste nommée : nom affiché -> liste(col, type, digits)
erp_table <- function(data, columns, page_length = 10, symbol = "") {
  if (is.null(data) || nrow(data) == 0) {
    return(div(class = "empty", span(class = "mark", "∅"), "Aucune ligne."))
  }
  keep <- vapply(columns, function(spec) spec$col, "")
  display <- data[, keep, drop = FALSE]
  names(display) <- names(columns)

  numeric_cols <- which(vapply(columns, function(spec)
    identical(spec$type, "num") || identical(spec$type, "money"), TRUE))

  table <- DT::datatable(
    display,
    rownames = FALSE,
    class = "compact stripe hover",
    options = list(
      pageLength = page_length,
      lengthChange = FALSE,
      dom = "tip",
      scrollX = TRUE,
      language = list(
        search = "Filtrer :", info = "_START_ à _END_ sur _TOTAL_ lignes",
        infoEmpty = "Aucune ligne", zeroRecords = "Aucun résultat",
        paginate = list(previous = "Précédent", `next` = "Suivant"))
    ),
    selection = "none"
  )
  for (i in numeric_cols) {
    digits <- columns[[i]]$digits %||% 0
    table <- DT::formatRound(table, names(columns)[i], digits = digits,
                             mark = " ", dec.mark = ",")
  }
  table
}

#' Description d'une colonne de tableau.
col_spec <- function(col, type = "text", digits = 0) {
  list(col = col, type = type, digits = digits)
}

#' Flux d'activité inter-départements.
activity_feed <- function(rows, symbol) {
  if (is.null(rows) || nrow(rows) == 0) {
    return(div(class = "empty", span(class = "mark", "∅"), "Aucune écriture."))
  }
  tags_map <- c(SALES = "VENTE", PURCH = "ACHAT", STOCK = "STOCK", FIN = "CHARGE")
  items <- lapply(seq_len(nrow(rows)), function(i) {
    row <- rows[i, ]
    amount <- if (row$dept == "STOCK") {
      sprintf("%+.0f u.", row$amount)
    } else {
      fmt_compact(row$amount, symbol)
    }
    label <- sub("^(Vente |Commande |Charge — )", "", row$label)
    when <- if (nchar(row$at) >= 16) {
      paste0(substr(row$at, 9, 10), "/", substr(row$at, 6, 7), " ", substr(row$at, 12, 16))
    } else row$at
    tag <- unname(tags_map[row$dept])          # NA si le code est inconnu
    if (is.na(tag)) tag <- row$dept
    div(class = "feed-row",
        span(class = "feed-tag",
             style = paste0("background:", dept_color(row$dept)), tag),
        span(class = "feed-label", title = row$label, label),
        span(class = "feed-amount", amount),
        span(class = "feed-time", when))
  })
  div(class = "feed", items)
}

#' Pastille de département (bandeau de la vue d'ensemble).
dept_chip <- function(code, name, value) {
  span(class = "dept-chip",
       span(class = "dept-dot", style = paste0("background:", dept_color(code))),
       tags$b(name), " · ", value)
}
