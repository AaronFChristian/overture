# Notifications at 50/80/100% of the $25 threshold (D-0028) -- not
# just a single alert at the limit, so there's warning before the
# cap is actually hit, not just after.

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-${local.name_prefix}"
  resource_group_id = azurerm_resource_group.main.id

  amount     = var.budget_amount_usd
  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
    end_date   = formatdate("YYYY-MM-01'T'00:00:00Z", timeadd(timestamp(), "8760h")) # ~1 year out
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }

  lifecycle {
    # timestamp()/timeadd() change on every plan -- without this,
    # Terraform would want to "update" the budget's time_period on
    # every single run just because "now" moved forward by however
    # many minutes since the last apply. Ignoring changes here means
    # the window is set once, at first apply, and left alone.
    ignore_changes = [time_period]
  }
}
