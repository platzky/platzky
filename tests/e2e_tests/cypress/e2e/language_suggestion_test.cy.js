// Stubs the browser's preferred languages, which the popup's script reads while the page loads.
const visitPreferring = (path, languages) =>
  cy.visit(path, {
    onBeforeLoad(win) {
      Object.defineProperty(win.navigator, 'languages', { value: languages })
    },
  })

describe('Language suggestion', () => {
  it('suggests the same page in the language the browser prefers', () => {
    visitPreferring('/blog/', ['pl-PL', 'en'])
    cy.get('.language-suggestion:visible')
      .should('have.length', 1)
      .and('have.attr', 'lang', 'pl')
      .find('a')
      .should('have.attr', 'href')
      .and('match', /\/pl\/blog\/$/)

    cy.get('.language-suggestion:visible a').click()

    cy.url().should('match', /\/pl\/blog\/$/)
    cy.get('#languages-menu').should('contain.text', 'pl')
  })

  it('stays hidden when the browser prefers the language of the page', () => {
    visitPreferring('/blog/', ['en-US', 'pl'])
    cy.get('.language-suggestion').should('exist')
    cy.get('.language-suggestion:visible').should('not.exist')

    visitPreferring('/pl/blog/', ['pl-PL', 'en'])
    cy.get('.language-suggestion').should('exist')
    cy.get('.language-suggestion:visible').should('not.exist')
  })

  it('stays hidden after the visitor closes it', () => {
    visitPreferring('/blog/', ['pl'])
    cy.get('.language-suggestion:visible .btn-close').click()
    cy.get('.language-suggestion:visible').should('not.exist')

    visitPreferring('/blog/', ['pl'])
    cy.get('.language-suggestion').should('exist')
    cy.get('.language-suggestion:visible').should('not.exist')
  })
})
