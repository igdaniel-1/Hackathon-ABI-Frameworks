import React from 'react';
import UserGrid from './UserGrid.tsx';
import USER_DATA from './userData.json'


function Dashboard() {
    return (
      <div>
        <p>
          Patient Dashboard
        </p>
        <div id="dashboardMainContainer">
            <UserGrid data={USER_DATA} /> 
        </div>
      </div>
    );
  }
  
  export default Dashboard;