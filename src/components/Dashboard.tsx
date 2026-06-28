import React from 'react';

function Dashboard() {
    return (
      <div>
        <p>
          Patient Dashboard
        </p>
        <div id="dashboardMainContainer">
            <div id="DashboardHeader">
                <p>Current Patient Claims</p>
            </div>
            <div id="DashboardBody">
                <div id="DashboardTitleRow"></div>
                <div id="DashboardDisplayUserGrid">
                    <li>user1</li>
                    <li>user2</li>
                    <li>user3</li>
                </div>
            </div>
            
        </div>
      </div>
    );
  }
  
  export default Dashboard;