# =====================================================================
#  Module d'accueil : le type de boutique et son nom suffisent à créer l'ERP.
# =====================================================================

onboarding_ui <- function(id) {
  ns <- NS(id)
  types <- CATALOG$types
  keys <- names(types)
  labels <- vapply(keys, function(k) types[[k]]$label, "")
  keys <- keys[order(labels)]

  currencies <- CATALOG$currencies
  currency_choices <- setNames(
    vapply(currencies, `[[`, "", "code"),
    vapply(currencies, function(c) sprintf("%s (%s)", c$label, c$symbol), ""))

  div(
    class = "onboard-page",
    div(
      class = "onboard",
      div(class = "onboard-mark", "ERP Boutique"),
      h1("Créez le tableau de bord de votre boutique"),
      tags$p(
        class = "lead",
        "Indiquez le type de commerce que vous exploitez et son nom. La plateforme ",
        "génère un ERP complet, ventes, stock, achats, clients, ressources humaines ",
        "et finance, dans une base SQL unique, avec un historique d'activité déjà ",
        "consolidé."),

      h2(class = "step-label", span(class = "step-num", "1"), "Quel type de boutique ?"),
      div(
        class = "type-grid",
        lapply(keys, function(key) {
          spec <- types[[key]]
          n_products <- sum(vapply(spec$categories, function(c) length(c$products), 0L))
          actionButton(
            inputId = ns(paste0("type_", key)),
            label = tagList(
              div(class = "type-icon", spec$icon),
              div(class = "type-name", spec$label),
              div(class = "type-tag", spec$tagline),
              div(class = "type-meta",
                  span(sprintf("%d rayons", length(spec$categories))),
                  span(sprintf("%d produits", n_products)),
                  span(sprintf("%d métiers", length(spec$roles))))),
            class = "type-card")
        })
      ),

      h2(class = "step-label", style = "margin-top:26px",
         span(class = "step-num", "2"), "Comment s'appelle-t-elle ?"),
      div(
        class = "grid grid-3",
        div(class = "field", textInput(ns("name"), "Nom de la boutique",
                                       placeholder = "Ex. : Chez Aminata", width = "100%")),
        div(class = "field", textInput(ns("city"), "Ville", value = "Abidjan", width = "100%")),
        div(class = "field", textInput(ns("country"), "Pays",
                                       value = "Côte d'Ivoire", width = "100%"))),

      tags$details(
        class = "advanced",
        tags$summary("Options avancées"),
        div(class = "grid grid-3",
            div(class = "field",
                selectInput(ns("currency"), "Devise", choices = currency_choices,
                            selected = "XOF", width = "100%")),
            div(class = "field",
                selectInput(ns("months"), "Profondeur d'historique",
                            choices = c("6 mois" = 6, "12 mois" = 12, "24 mois" = 24),
                            selected = 12, width = "100%")),
            div(class = "field",
                selectInput(ns("traffic"), "Intensité d'activité",
                            choices = c("Petit commerce (×0,4)" = 0.4,
                                        "Activité normale (×1)" = 1,
                                        "Forte affluence (×2)" = 2),
                            selected = 1, width = "100%")))),

      uiOutput(ns("notice")),

      div(style = "display:flex;align-items:center;gap:14px;margin-top:18px",
          actionButton(ns("create"), "Créer mon tableau de bord", class = "btn"),
          textOutput(ns("echo"), inline = TRUE))
    )
  )
}

#' @param on_created fonction appelée après création (pour basculer l'application).
onboarding_server <- function(id, con, on_created) {
  moduleServer(id, function(input, output, session) {
    selected <- reactiveVal(NULL)
    keys <- names(CATALOG$types)

    # Un observateur par vignette : le clic mémorise le type choisi.
    lapply(keys, function(key) {
      # `ignoreNULL = TRUE` (défaut) suffit à ignorer la valeur initiale du
      # bouton : inutile d'y ajouter `ignoreInit`, qui ferait en plus perdre
      # le tout premier clic dans un cycle réactif encore vierge.
      observeEvent(input[[paste0("type_", key)]], {
        selected(key)
        session$sendCustomMessage("erp-select-type",
                                  list(id = session$ns(paste0("type_", key))))
      })
    })

    output$echo <- renderText({
      if (is.null(selected())) return("Choisissez d'abord un type de boutique.")
      if (!nzchar(trimws(input$name %||% ""))) {
        return("Indiquez maintenant le nom de la boutique.")
      }
      sprintf("Prêt : « %s ».", trimws(input$name))
    })

    output$notice <- renderUI({
      div(class = "notice notice-info",
          div(tags$b("Les six départements sont livrés d'office. "),
              "Ils partagent une seule base de données : une vente décharge le stock, ",
              "met à jour la fiche client et le compte de résultat au même instant."))
    })

    observeEvent(input$create, {
      type <- selected()
      name <- trimws(input$name %||% "")
      if (is.null(type)) {
        showNotification("Sélectionnez le type de boutique (étape 1).",
                         type = "warning", duration = 6)
        return()
      }
      if (!nzchar(name)) {
        showNotification("Le nom de la boutique est obligatoire (étape 2).",
                         type = "warning", duration = 6)
        return()
      }

      progress <- shiny::Progress$new(session, min = 0, max = 1)
      on.exit(progress$close())
      progress$set(message = "Création de l'ERP", value = 0.02)

      summary <- generate_company(
        con, name, type,
        currency = input$currency, city = input$city, country = input$country,
        history_months = as.integer(input$months),
        traffic_scale = as.numeric(input$traffic),
        progress = function(message, value) progress$set(detail = message, value = value))

      showNotification(
        sprintf("« %s » créée : %s tickets générés.",
                summary$company, fr_num(summary$sales)),
        type = "message", duration = 8)
      on_created(summary)
    })
  })
}
