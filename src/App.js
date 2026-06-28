import './App.css';
import UserGrid from './components/UserGrid.tsx';
import USER_DATA from './components/userData.json'
// import Dashboard from './components/Dashboard.tsx';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <UserGrid data={USER_DATA} /> 
      </header>
    </div>
  );
}

export default App;
