# =====================================================================
#  ERP Boutique — dashboard R Shiny
#
#  Lancement :
#      cd shiny && Rscript -e "shiny::runApp('.', port = 3838)"
#  ou depuis RStudio : ouvrir app.R puis « Run App ».
#
#  Au premier démarrage, la base est vide : l'écran d'accueil demande le
#  type de boutique et son nom, puis génère l'ERP complet. Les six
#  départements lisent ensuite la même base SQL centrale.
# =====================================================================

# Shiny source automatiquement global.R ; ce garde-fou permet aussi
# de lancer l'application avec shiny::runApp("chemin/vers/shiny").
if (!exists("CATALOG")) source("global.R", encoding = "UTF-8")

# ---------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------
ui <- function(request) {
  tagList(
    tags$head(
      tags$title("ERP Boutique — tableau de bord"),
      tags$meta(name = "viewport", content = "width=device-width, initial-scale=1"),
      tags$link(rel = "stylesheet", href = "styles.css"),
      tags$script(HTML("
        // Met en évidence la vignette de métier choisie à l'écran d'accueil.
        Shiny.addCustomMessageHandler('erp-select-type', function(message) {
          document.querySelectorAll('.type-card').forEach(function(card) {
            card.classList.toggle('selected', card.id === message.id);
          });
        });
      "))
    ),
    uiOutput("application")
  )
}

# ---------------------------------------------------------------------
# Serveur
# ---------------------------------------------------------------------
server <- function(input, output, session) {
  con <- db_connect()
  onStop(function() DBI::dbDisconnect(con))

  configured <- reactiveVal(db_is_configured(con))
  period <- reactiveVal(30)

  # --- Aiguillage : accueil ou tableau de bord -----------------------
  output$application <- renderUI({
    if (!configured()) {
      onboarding_ui("onboarding")
    } else {
      dashboard_ui(db_company(con))
    }
  })

  onboarding_server("onboarding", con, on_created = function(summary) {
    configured(TRUE)
  })

  # --- Barre supérieure : période analysée ---------------------------
  observeEvent(input$period, {
    period(as.integer(input$period))
  }, ignoreInit = TRUE)

  # --- Modules des départements --------------------------------------
  overview_server("overview", con, period)
  sales_server("sales", con, period)
  stock_server("stock", con, period)
  purchasing_server("purchasing", con, period)
  crm_server("crm", con, period)
  hr_server("hr", con, period)
  finance_server("finance", con, period)

  # --- Réinitialisation ----------------------------------------------
  observeEvent(input$reset, {
    showModal(modalDialog(
      title = "Réinitialiser la plateforme ?",
      "Toutes les données de la boutique seront effacées : ventes, stock, achats, ",
      "clients, personnel et écritures financières.",
      footer = tagList(
        modalButton("Annuler"),
        actionButton("reset_confirm", "Tout effacer", class = "btn btn-danger")),
      easyClose = TRUE))
  })

  observeEvent(input$reset_confirm, {
    removeModal()
    db_reset(con)
    configured(FALSE)
    showNotification("Plateforme réinitialisée.", type = "message", duration = 5)
  })
}

#' Coquille du tableau de bord : barre latérale, barre supérieure, onglets.
dashboard_ui <- function(company) {
  bslib::page_navbar(
    id = "nav",
    title = div(
      class = "brand",
      span(class = "brand-logo", company$logo_emoji),
      div(div(class = "brand-name", company$name),
          div(class = "brand-type", company$store_label))),
    theme = erp_theme(),
    fillable = FALSE,
    header = div(
      class = "topbar",
      span(class = "muted", "Période analysée"),
      radioButtons("period", label = NULL, inline = TRUE,
                   choices = c("7 jours" = 7, "30 jours" = 30,
                               "90 jours" = 90, "12 mois" = 365),
                   selected = 30),
      span(class = "topbar-meta",
           sprintf("Base SQL centrale · %s · TVA %s %%",
                   company$currency, fr_num(company$tax_rate * 100, 0))),
      actionButton("reset", "Réinitialiser", class = "btn btn-danger btn-sm")),
    nav_panel(title = "\U0001F4CA Vue d'ensemble", overview_ui("overview")),
    nav_panel(title = "\U0001F9FE Ventes",         sales_ui("sales")),
    nav_panel(title = "\U0001F4E6 Stock",          stock_ui("stock")),
    nav_panel(title = "\U0001F69A Achats",         purchasing_ui("purchasing")),
    nav_panel(title = "\U0001F465 Clients",        crm_ui("crm")),
    nav_panel(title = "\U0001F9D1 Ressources humaines", hr_ui("hr")),
    nav_panel(title = "\U0001F4B0 Finance",        finance_ui("finance"))
  )
}

shinyApp(ui, server)
