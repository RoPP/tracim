import { login, logout } from '../helpers/index.js'

describe('content :: admin > workspace', function () {
    before(function () {
        login(cy)
        cy.get('.adminlink__btn.dropdown-toggle').click()
        cy.get('a.setting__link[href="/admin/workspace"]').click()
        cy.url().should('include', '/admin/workspace')
    })
    after(function() {
        logout (cy)
    })
    it ('', function(){
        cy.get('.adminWorkspace__description').should('be.visible')
        cy.get('.adminWorkspace__delimiter').should('be.visible')
        cy.get('.adminWorkspace__workspaceTable').should('be.visible')
    })
    it ('content of workspaceTable', function(){
        cy.get('.adminWorkspace__workspaceTable th:nth-child(1)[scope="col"]').should('be.visible')
        cy.get('.adminWorkspace__workspaceTable th:nth-child(2)[scope="col"]').should('be.visible')
        cy.get('.adminWorkspace__workspaceTable th:nth-child(3)[scope="col"]').should('be.visible')
        cy.get('.adminWorkspace__workspaceTable th:nth-child(4)[scope="col"]').should('be.visible')
        cy.get('.adminWorkspace__workspaceTable th:nth-child(5)[scope="col"]').should('be.visible')
    })
})